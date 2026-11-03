#include <cassert>
#include <cstdint>
#include <iostream>

#include "../ui_fivepage_candidate/board_package/touch_geometry.hpp"

int main() {
    using namespace ui_touch;
    static_assert(kTabCount == 5, "final UI must have five tabs");

    const int centers[5] = {128, 384, 640, 896, 1152};
    for (int i = 0; i < 5; ++i) {
        assert(nav_tab_from_point(centers[i], 675, 1280, 720) == i);
    }
    assert(nav_tab_from_point(-1, 675, 1280, 720) == -1);
    assert(nav_tab_from_point(1280, 675, 1280, 720) == -1);
    assert(nav_tab_from_point(640, 629, 1280, 720) == -1);

    TouchNav nav(1280, 720, 0);
    for (int i = 0; i < 5; ++i) {
        Point p{centers[i], 675, true};
        nav.on_sample(true, p, 100 + i * 10);
        nav.on_sample(false, p, 101 + i * 10);
        assert(nav.active_page() == i);
    }
    assert(nav.tap_count() == 5);
    std::cout << "FIVEPAGE_NAV_TEST result=PASS tabs=5\n";
    return 0;
}
