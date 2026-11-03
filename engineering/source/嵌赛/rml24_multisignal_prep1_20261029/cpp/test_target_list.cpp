// test_target_list.cpp -- host test for the C2 target-list parser + state.
//
// Build (WSL, host only -- NOT aarch64):
//   g++ -std=c++17 -Wall -Wextra -I. test_target_list.cpp -o test_target_list
//   ./test_target_list
//
// Exercises the strict rml24_targets parser (accepts the valid wire form and
// rejects malformed/non-standard input) and the list-page state model (sort,
// pagination, selection, clear-old-IQ on switch/expire/unclassify, "未分类").

#include "target_list_rml24_parse.hpp"
#include "target_list_state.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>

static int failures = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        if (!(cond)) {                                                  \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
            ++failures;                                                 \
        }                                                               \
    } while (0)

using ui::TargetListEvent;
using ui::TargetListState;

static TargetListEvent parse_ok(const std::string& s) {
    TargetListEvent ev = ui::parse_rml24_targets(s);
    CHECK(ev.ok);
    if (!ev.ok) std::printf("  error: %s\n", ev.error.c_str());
    return ev;
}

static void parse_reject(const std::string& s) {
    TargetListEvent ev = ui::parse_rml24_targets(s);
    CHECK(!ev.ok);
    CHECK(!ev.error.empty());
}

int main() {
    // ---- valid: two targets, one classified (numeric power), one unclassified
    //      (null power, empty top3, confidence 0.0) ---------------------------
    const std::string good =
        "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
        "\"timestamp_us\":1700000000000000,"
        "\"targets\":["
        "{\"target_id\":1,\"center_hz\":2400000000,\"bw_hz\":0,"
        "\"power_valid\":null,\"top3\":[{\"class_name\":\"QPSK\",\"confidence\":0.866}],"
        "\"confidence\":0.866,\"last_seen\":12.5,\"status\":\"tracking\",\"backend\":\"software\"},"
        "{\"target_id\":2,\"center_hz\":2400500000,\"bw_hz\":2500,"
        "\"power_valid\":21.5,\"top3\":[],"
        "\"confidence\":0.0,\"last_seen\":11.0,\"status\":\"new\",\"backend\":\"fpga\"}"
        "]}";
    TargetListEvent ev = parse_ok(good);
    CHECK(ev.targets.size() == 2);
    CHECK(ev.targets[0].target_id == 1);
    CHECK(ev.targets[0].power_valid_present == false);       // null -> unmeasured
    CHECK(ev.targets[0].classified());
    CHECK(ev.targets[0].top3.front().class_name == "QPSK");
    CHECK(ev.targets[1].power_valid_present == true);        // numeric PSD power
    CHECK(ev.targets[1].power_valid == 21.5);
    CHECK(!ev.targets[1].classified());                       // 未分类

    // ---- empty target list is VALID (no signal) -----------------------------
    const std::string empty_list =
        "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
        "\"timestamp_us\":5,\"targets\":[]}";
    TargetListEvent e2 = parse_ok(empty_list);
    CHECK(e2.targets.empty());

    // ---- rejections (fail-closed) -------------------------------------------
    parse_reject("{\"type\":\"result\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":5,\"targets\":[]}");                       // wrong type
    parse_reject("{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":5,\"targets\":[]}junk");                   // trailing content
    parse_reject("{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":5,\"targets\":[{\"target_id\":1,\"center_hz\":2400000000,"
                 "\"bw_hz\":0,\"power_valid\":NaN,\"top3\":[],\"confidence\":0.0,"
                 "\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"}]}"); // NaN not JSON
    parse_reject("{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":5,\"targets\":[{\"target_id\":1,\"center_hz\":2400000000,"
                 "\"bw_hz\":0,\"power_valid\":null,\"top3\":[],\"confidence\":0.5,"
                 "\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"}]}"); // unclassified w/ conf!=0
    parse_reject("{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":5,\"targets\":[{\"target_id\":1,\"center_hz\":2400000000,"
                 "\"bw_hz\":0,\"power_valid\":null,\"top3\":[],\"confidence\":0.0,"
                 "\"last_seen\":1.0,\"status\":\"bogus\",\"backend\":\"software\"}]}"); // unknown status
    parse_reject("{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":5,\"targets\":[{\"target_id\":1,\"center_hz\":2400000000,"
                 "\"bw_hz\":0,\"power_valid\":null,"
                 "\"top3\":[{\"class_name\":\"A\",\"confidence\":0.1},"
                 "{\"class_name\":\"B\",\"confidence\":0.1},"
                 "{\"class_name\":\"C\",\"confidence\":0.1},"
                 "{\"class_name\":\"D\",\"confidence\":0.1}],"
                 "\"confidence\":0.0,\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"}]}"); // top3 > 3
    parse_reject("{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
                 "\"timestamp_us\":-5,\"targets\":[]}");                       // negative timestamp

    // ---- state: sort / summary / selection / clear-old-IQ -------------------
    TargetListState st;
    st.apply(ev);
    CHECK(st.size() == 2);
    CHECK(!st.empty());
    CHECK(st.summary_line() == "targets=2");
    CHECK(st.update_time_us() == 1700000000000000ull);

    // Sorted by centre frequency: 2400000000 (id 1) before 2400500000 (id 2).
    std::vector<const ui::TargetRecord*> page = st.visible_page();
    CHECK(page.size() == 2);
    CHECK(page[0]->center_hz == 2400000000ull);

    // Select the classified target -> valid data.
    ui::SelectFeedback f = st.select(1);
    CHECK(f.ok);
    CHECK(st.selected_target_id() == 1);
    CHECK(st.selected_has_valid_data());
    CHECK(st.selected_top1_label() == "QPSK");

    // Switch to the unclassified target -> params cleared, label "未分类".
    f = st.select(2);
    CHECK(f.ok);
    CHECK(st.selected_target_id() == 2);
    CHECK(!st.selected_has_valid_data());                   // no fabricated data
    CHECK(st.selected_top1_label() == std::string(ui::unclassified_label()));
    CHECK(!st.selected_top1_label().empty());

    // Unknown selection is rejected with feedback and leaves selection intact.
    f = st.select(99);
    CHECK(!f.ok);
    CHECK(f.error == "unknown target_id");
    CHECK(st.selected_target_id() == 2);

    // Selection vanishes -> falls back to none and clears params.
    const std::string only_one =
        "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
        "\"timestamp_us\":6,\"targets\":["
        "{\"target_id\":1,\"center_hz\":2400000000,\"bw_hz\":0,\"power_valid\":null,"
        "\"top3\":[{\"class_name\":\"QPSK\",\"confidence\":0.866}],"
        "\"confidence\":0.866,\"last_seen\":13.0,\"status\":\"tracking\",\"backend\":\"software\"}]}";
    st.apply(parse_ok(only_one));
    CHECK(st.selected_target_id() == -1);
    CHECK(!st.selected_has_valid_data());

    // A target that becomes unclassified clears a valid selection.
    st.select(1);
    CHECK(st.selected_has_valid_data());
    const std::string now_unclassified =
        "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
        "\"timestamp_us\":7,\"targets\":["
        "{\"target_id\":1,\"center_hz\":2400000000,\"bw_hz\":0,\"power_valid\":null,"
        "\"top3\":[],\"confidence\":0.0,\"last_seen\":14.0,\"status\":\"missing\",\"backend\":\"software\"}]}";
    st.apply(parse_ok(now_unclassified));
    CHECK(st.selected_target_id() == -1);
    CHECK(!st.selected_has_valid_data());

    // ---- pagination overflow ------------------------------------------------
    TargetListState st2;
    st2.set_page_size(2);
    const std::string four =
        "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
        "\"timestamp_us\":8,\"targets\":["
        "{\"target_id\":1,\"center_hz\":2400000000,\"bw_hz\":0,\"power_valid\":null,\"top3\":[],\"confidence\":0.0,\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"},"
        "{\"target_id\":2,\"center_hz\":2401000000,\"bw_hz\":0,\"power_valid\":null,\"top3\":[],\"confidence\":0.0,\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"},"
        "{\"target_id\":3,\"center_hz\":2402000000,\"bw_hz\":0,\"power_valid\":null,\"top3\":[],\"confidence\":0.0,\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"},"
        "{\"target_id\":4,\"center_hz\":2403000000,\"bw_hz\":0,\"power_valid\":null,\"top3\":[],\"confidence\":0.0,\"last_seen\":1.0,\"status\":\"new\",\"backend\":\"software\"}"
        "]}";
    st2.apply(parse_ok(four));
    CHECK(st2.page_count() == 2);
    CHECK(st2.visible_page().size() == 2);
    st2.set_page_offset(1);
    CHECK(st2.visible_page().size() == 2);
    CHECK(st2.visible_page().front()->center_hz == 2402000000ull);
    st2.set_page_offset(99);                                 // clamped
    CHECK(st2.page_offset() == 1);

    if (failures == 0) {
        std::printf("ALL CHECKS PASSED\n");
        return 0;
    }
    std::printf("%d CHECK(S) FAILED\n", failures);
    return 1;
}
