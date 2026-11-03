// test_target_list_ui.cpp -- host unit test for the C-line multi-target UI wiring.
//
// Covers the three header-only pieces that are host-testable without the board's
// iCraft/libiio/framebuffer stack:
//
//   1. ui::parse_rml24_targets  (target_list_rml24_parse.hpp) -- valid / invalid
//      rml24_targets JSON lines, fail-closed contract enforcement.
//   2. ui::TargetListState       (target_list_state.hpp) -- sort by centre
//      frequency, pagination, selection, clear-on-vanish/expire/unclassify, the
//      unclassified label.
//   3. ui::dispatch_targets_line (target_list_dispatch.hpp) -- event-line routing:
//      Valid / Rejected / NotATargetsLine, so a valid targets line never reaches
//      the rejected/state_rejected path and a malformed targets line is not
//      counted as a state rejection.
//
// The board main program (board_ui_live_rml24_final.cpp) and the renderers depend
// on board-only headers and are NOT compiled here (see the integration doc).

#include "target_list_state.hpp"
#include "target_list_dispatch.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>

static int g_checks = 0;
static int g_failures = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        ++g_checks;                                                     \
        if (!(cond)) {                                                  \
            ++g_failures;                                               \
            std::printf("FAIL %s:%d  %s\n", __FILE__, __LINE__, #cond); \
        }                                                               \
    } while (0)

static std::string target_line(const std::string& inner) {
    return "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
           "\"timestamp_us\":42,\"targets\":[" + inner + "]}";
}

static std::string rec(const std::string& id, const std::string& center,
                       const std::string& top3, const std::string& conf,
                       const std::string& status, const std::string& backend) {
    return "{\"target_id\":" + id + ",\"center_hz\":" + center +
           ",\"bw_hz\":2000000,\"power_valid\":12.5,\"top3\":" + top3 +
           ",\"confidence\":" + conf + ",\"last_seen\":1.5,\"status\":\"" +
           status + "\",\"backend\":\"" + backend + "\"}";
}

int main() {
    using namespace ui;

    // ---- 1. parser: valid lines -------------------------------------------
    {
        TargetListEvent ev = parse_rml24_targets(target_line(""));
        CHECK(ev.ok);
        CHECK(ev.version == "rml24-multisignal-v1");
        CHECK(ev.timestamp_us == 42);
        CHECK(ev.targets.empty());   // empty targets array is VALID (no signal)
    }
    {
        TargetListEvent ev = parse_rml24_targets(target_line(
            rec("1", "2400000000",
                "[{\"class_name\":\"QPSK\",\"confidence\":0.9},"
                "{\"class_name\":\"8PSK\",\"confidence\":0.05}]",
                "0.9", "tracking", "software")));
        CHECK(ev.ok);
        CHECK(ev.targets.size() == 1);
        const TargetRecord& t = ev.targets[0];
        CHECK(t.target_id == 1);
        CHECK(t.center_hz == 2400000000ULL);
        CHECK(t.bw_hz == 2000000ULL);
        CHECK(t.power_valid_present);
        CHECK(t.power_valid == 12.5);
        CHECK(t.top3.size() == 2);
        CHECK(t.top3[0].class_name == "QPSK");
        CHECK(t.classified());
        CHECK(t.status == "tracking");
        CHECK(t.backend == "software");
    }
    {
        // Unclassified: empty top3 + confidence 0.0; power_valid null -> unmeasured.
        TargetListEvent ev = parse_rml24_targets(target_line(
            "{\"target_id\":2,\"center_hz\":2390000000,\"bw_hz\":0,"
            "\"power_valid\":null,\"top3\":[],\"confidence\":0.0,"
            "\"last_seen\":0.0,\"status\":\"new\",\"backend\":\"fpga\"}"));
        CHECK(ev.ok);
        const TargetRecord& t = ev.targets[0];
        CHECK(!t.power_valid_present);
        CHECK(t.top3.empty());
        CHECK(!t.classified());
        CHECK(t.confidence == 0.0);
    }

    // ---- 2. parser: invalid lines (fail-closed, non-empty error) ----------
    {
        TargetListEvent ev = parse_rml24_targets(
            "{\"type\":\"state\",\"version\":\"rml24-standalone-state-v1\","
            "\"timestamp_us\":1,\"work_mode\":\"FIXED\"}");
        CHECK(!ev.ok);
        CHECK(!ev.error.empty());
    }
    {
        // missing targets field
        TargetListEvent ev = parse_rml24_targets(
            "{\"type\":\"rml24_targets\",\"version\":\"rml24-multisignal-v1\","
            "\"timestamp_us\":1}");
        CHECK(!ev.ok && !ev.error.empty());
    }
    {
        // confidence out of [0,1]
        TargetListEvent ev = parse_rml24_targets(target_line(
            rec("1", "2400000000", "[{\"class_name\":\"QPSK\",\"confidence\":0.9}]",
                "1.5", "tracking", "software")));
        CHECK(!ev.ok && !ev.error.empty());
    }
    {
        // unclassified target must carry confidence 0.0
        TargetListEvent ev = parse_rml24_targets(target_line(
            "{\"target_id\":1,\"center_hz\":2400000000,\"bw_hz\":0,"
            "\"power_valid\":null,\"top3\":[],\"confidence\":0.7,"
            "\"last_seen\":0.0,\"status\":\"new\",\"backend\":\"auto\"}"));
        CHECK(!ev.ok && !ev.error.empty());
    }
    {
        // unknown status token
        TargetListEvent ev = parse_rml24_targets(target_line(
            rec("1", "2400000000", "[]", "0.0", "zombie", "auto")));
        CHECK(!ev.ok && !ev.error.empty());
    }
    {
        // unknown backend token
        TargetListEvent ev = parse_rml24_targets(target_line(
            rec("1", "2400000000", "[]", "0.0", "new", "quantum")));
        CHECK(!ev.ok && !ev.error.empty());
    }
    {
        // top3 longer than three
        TargetListEvent ev = parse_rml24_targets(target_line(
            "{\"target_id\":1,\"center_hz\":2400000000,\"bw_hz\":0,"
            "\"power_valid\":1.0,"
            "\"top3\":[{\"class_name\":\"A\",\"confidence\":0.5},"
            "{\"class_name\":\"B\",\"confidence\":0.2},"
            "{\"class_name\":\"C\",\"confidence\":0.1},"
            "{\"class_name\":\"D\",\"confidence\":0.05}],"
            "\"confidence\":0.5,\"last_seen\":0.0,\"status\":\"new\","
            "\"backend\":\"auto\"}"));
        CHECK(!ev.ok && !ev.error.empty());
    }
    {
        // trailing content
        TargetListEvent ev = parse_rml24_targets(target_line("") + "garbage");
        CHECK(!ev.ok && !ev.error.empty());
    }

    // ---- 3. TargetListState: sort / paginate / select / clear --------------
    TargetListState st;
    CHECK(st.empty());
    CHECK(st.size() == 0);
    CHECK(st.summary_line() == "targets=0");

    TargetListEvent seven = parse_rml24_targets(target_line(
        rec("1", "2400000000", "[{\"class_name\":\"QPSK\",\"confidence\":0.9}]", "0.9", "tracking", "software") + "," +
        rec("2", "2390000000", "[{\"class_name\":\"BPSK\",\"confidence\":0.8}]", "0.8", "tracking", "software") + "," +
        rec("3", "2410000000", "[{\"class_name\":\"8PSK\",\"confidence\":0.7}]", "0.7", "new", "fpga") + "," +
        rec("4", "2380000000", "[]", "0.0", "new", "software") + "," +
        rec("5", "2420000000", "[{\"class_name\":\"16QAM\",\"confidence\":0.6}]", "0.6", "tracking", "auto") + "," +
        rec("6", "2370000000", "[{\"class_name\":\"2FSK\",\"confidence\":0.5}]", "0.5", "tracking", "software") + "," +
        rec("7", "2430000000", "[{\"class_name\":\"64QAM\",\"confidence\":0.4}]", "0.4", "tracking", "software")));
    CHECK(seven.ok);
    st.apply(seven);
    CHECK(st.size() == 7);
    CHECK(st.summary_line() == "targets=7");
    // sorted ascending by centre frequency: 2370, 2380, 2390, 2400, 2410, 2420, 2430 MHz
    {
        const std::vector<const TargetRecord*> page = st.visible_page();
        CHECK(page.size() == 6);   // default page size 6
        CHECK(page[0]->center_hz == 2370000000ULL);
        CHECK(page[1]->center_hz == 2380000000ULL);
        CHECK(page[2]->center_hz == 2390000000ULL);
        CHECK(page[3]->center_hz == 2400000000ULL);
        CHECK(page[4]->center_hz == 2410000000ULL);
        CHECK(page[5]->center_hz == 2420000000ULL);
    }
    CHECK(st.page_count() == 2);
    CHECK(st.page_offset() == 0);
    st.set_page_offset(1);
    {
        const std::vector<const TargetRecord*> page = st.visible_page();
        CHECK(page.size() == 1);
        CHECK(page[0]->center_hz == 2430000000ULL);
    }
    st.set_page_offset(99);   // clamps to last page
    CHECK(st.page_offset() == 1);
    st.set_page_offset(0);

    // selection (select takes target_id)
    st.clear_selection();
    SelectFeedback f = st.select(1ULL);
    CHECK(f.ok);
    CHECK(f.selected_target_id == 1);
    CHECK(st.selected_target_id() == 1);
    const TargetRecord* sel = st.selected();
    CHECK(sel != nullptr && sel->target_id == 1);
    CHECK(st.selected_has_valid_data());
    CHECK(st.selected_top1_label() == "QPSK");

    // selecting an unclassified target is accepted but has no valid params/IQ
    SelectFeedback f4 = st.select(4ULL);
    CHECK(f4.ok);
    CHECK(!st.selected_has_valid_data());
    CHECK(st.selected_top1_label() == unclassified_label());
    CHECK(std::string(unclassified_label()) == "\xE6\x9C\xAA\xE5\x88\x86\xE7\xB1\xBB");

    // selecting an expired target is accepted but has no valid params/IQ
    TargetListEvent expired = parse_rml24_targets(target_line(
        "{\"target_id\":9,\"center_hz\":2395000000,\"bw_hz\":0,"
        "\"power_valid\":1.0,\"top3\":[{\"class_name\":\"GMSK\",\"confidence\":0.5}],"
        "\"confidence\":0.5,\"last_seen\":0.0,\"status\":\"expired\","
        "\"backend\":\"auto\"}"));
    CHECK(expired.ok);
    st.apply(expired);
    SelectFeedback f9 = st.select(9ULL);
    CHECK(f9.ok);
    CHECK(!st.selected_has_valid_data());

    // unknown target_id
    SelectFeedback bad = st.select(12345ULL);
    CHECK(!bad.ok);
    CHECK(bad.error == "unknown target_id");

    // vanish: apply an event without the selected target -> selection cleared
    st.apply(seven);
    st.select(1ULL);
    CHECK(st.selected_has_valid_data());
    TargetListEvent none = parse_rml24_targets(target_line(""));
    CHECK(none.ok);
    st.apply(none);
    CHECK(st.selected() == nullptr);
    CHECK(!st.selected_has_valid_data());

    // re-apply seven, select id 2, then apply an event where id 2 becomes
    // unclassified -> selection cleared (params no longer valid)
    st.apply(seven);
    st.select(2ULL);
    CHECK(st.selected_has_valid_data());
    TargetListEvent unclass2 = parse_rml24_targets(target_line(
        rec("2", "2390000000", "[]", "0.0", "tracking", "software")));
    CHECK(unclass2.ok);
    st.apply(unclass2);
    CHECK(st.selected() == nullptr);
    CHECK(!st.selected_has_valid_data());

    st.clear_selection();
    CHECK(st.selected_target_id() == -1);
    CHECK(!st.selected_has_valid_data());

    // ---- 4. dispatch: event-line routing -----------------------------------
    {
        // valid targets line -> Valid, never rejected/state_rejected
        TargetsDispatchOutcome o = dispatch_targets_line(target_line(
            rec("1", "2400000000", "[{\"class_name\":\"QPSK\",\"confidence\":0.9}]",
                "0.9", "tracking", "software")));
        CHECK(o.kind == TargetsDispatchOutcome::Kind::Valid);
        CHECK(o.event.ok);
        CHECK(o.event.targets.size() == 1);
    }
    {
        // malformed targets line -> Rejected (counted rejected, NOT state_rejected)
        TargetsDispatchOutcome o = dispatch_targets_line(target_line(
            rec("1", "2400000000", "[{\"class_name\":\"QPSK\",\"confidence\":0.9}]",
                "1.5", "tracking", "software")));   // confidence > 1
        CHECK(o.kind == TargetsDispatchOutcome::Kind::Rejected);
        CHECK(!o.event.ok && !o.event.error.empty());
    }
    {
        // state line -> NotATargetsLine (falls through to state branch)
        TargetsDispatchOutcome o = dispatch_targets_line(
            "{\"type\":\"state\",\"version\":\"rml24-standalone-state-v1\","
            "\"command_id\":0,\"work_mode\":\"BAND_SCAN\",\"run_state\":\"RUNNING\","
            "\"presence_state\":\"SIGNAL_PRESENT\",\"timestamp_us\":1}");
        CHECK(o.kind == TargetsDispatchOutcome::Kind::NotATargetsLine);
    }
    {
        // result line -> NotATargetsLine
        TargetsDispatchOutcome o = dispatch_targets_line(
            "{\"type\":\"result\",\"version\":\"rml24-final-chain-v1\",\"frame_id\":1}");
        CHECK(o.kind == TargetsDispatchOutcome::Kind::NotATargetsLine);
    }
    {
        // non-JSON garbage -> NotATargetsLine
        TargetsDispatchOutcome o = dispatch_targets_line("not json at all");
        CHECK(o.kind == TargetsDispatchOutcome::Kind::NotATargetsLine);
    }
    {
        // "type" key NOT first (order-independent sniff) -> still Valid
        TargetsDispatchOutcome o = dispatch_targets_line(
            "{\"version\":\"rml24-multisignal-v1\",\"type\":\"rml24_targets\","
            "\"timestamp_us\":7,\"targets\":[]}");
        CHECK(o.kind == TargetsDispatchOutcome::Kind::Valid);
        CHECK(o.event.ok && o.event.targets.empty());
    }
    {
        // a nested object containing "type":"rml24_targets" but whose TOP-LEVEL
        // type is something else must NOT be misrouted (depth-counting sniff).
        TargetsDispatchOutcome o = dispatch_targets_line(
            "{\"type\":\"state\",\"version\":\"v1\",\"nested\":"
            "{\"type\":\"rml24_targets\",\"targets\":[]}}");
        CHECK(o.kind == TargetsDispatchOutcome::Kind::NotATargetsLine);
    }

    // ---- summary -----------------------------------------------------------
    if (g_failures == 0) {
        std::printf("ALL CHECKS PASSED (%d checks)\n", g_checks);
        return 0;
    }
    std::printf("CHECKS FAILED: %d/%d\n", g_failures, g_checks);
    return 1;
}
