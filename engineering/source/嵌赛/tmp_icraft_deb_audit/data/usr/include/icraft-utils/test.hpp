#ifdef _BAREME  

#include <cassert>
using namespace icraft::xir;

#define TEST_CASE(caseName, tags) void test_case() 
#define REQUIRE(...) assert(##__VA_ARGS__)


#else // no bareme

#include <catch2/catch.hpp>

#define TEST_CASE(caseName, tags) TEST_CASE( #caseName, tags) 

#endif  // #ifndef _BAREME


