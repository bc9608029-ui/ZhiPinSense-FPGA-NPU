#include "../ui_overlay/board_package/touch_geometry.hpp"

#include <cassert>

int main() {
    using namespace ui_touch;
    static_assert(kTabCount == 4, "final dual-mode UI must have four tabs");
    assert(nav_tab_from_point(0, 700, 1280, 720) == 0);
    assert(nav_tab_from_point(319, 700, 1280, 720) == 0);
    assert(nav_tab_from_point(320, 700, 1280, 720) == 1);
    assert(nav_tab_from_point(640, 700, 1280, 720) == 2);
    assert(nav_tab_from_point(960, 700, 1280, 720) == 3);
    assert(nav_tab_from_point(1279, 700, 1280, 720) == 3);
    assert(nav_tab_from_point(1279, 620, 1280, 720) == -1);
    return 0;
}

