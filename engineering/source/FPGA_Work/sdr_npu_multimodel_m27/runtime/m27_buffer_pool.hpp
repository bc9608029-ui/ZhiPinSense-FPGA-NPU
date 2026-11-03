// M27 fixed input/output buffer pool (spec §八): no per-frame allocation, explicit
// ownership, bounds-checked acquire/release.  header-only, namespace m27.
//
// Buffers are a fixed count of fixed-size byte slots allocated once at construction.
// Each slot carries an owner tag (0 = free, else 1+slot-owner id) so a release by the
// wrong owner, a double release, or an out-of-range index is detected and reported
// (fail-closed) instead of silently corrupting shared memory.
#ifndef M27_BUFFER_POOL_HPP
#define M27_BUFFER_POOL_HPP

#include <cstdint>
#include <cstddef>
#include <vector>
#include <cstring>

namespace m27 {

class BufferPool {
 public:
  BufferPool() = default;

  // Allocate exactly `count` slots of `slot_bytes` each, zeroed, all free.
  // Returns false (and leaves the pool empty) on any failure.  Steady-state use of
  // the pool performs no further allocation.
  bool init(std::size_t count, std::size_t slot_bytes) {
    if (count == 0 || slot_bytes == 0) return false;
    count_ = count;
    slot_bytes_ = slot_bytes;
    data_.assign(count * slot_bytes, 0);
    owner_.assign(count, 0);
    return true;
  }

  std::size_t count() const { return count_; }
  std::size_t slot_bytes() const { return slot_bytes_; }

  // Acquire a free slot, marking it owned by `owner` (non-zero).  Returns -1 if no
  // free slot remains (backpressure signal to the scheduler).
  int acquire(std::uint32_t owner) {
    if (owner == 0) return -1;
    for (std::size_t i = 0; i < count_; ++i) {
      if (owner_[i] == 0) {
        owner_[i] = owner;
        std::memset(data_.data() + i * slot_bytes_, 0, slot_bytes_);
        return static_cast<int>(i);
      }
    }
    return -1;
  }

  // Release a slot back to the pool.  Fails (returns false) on out-of-range index,
  // wrong owner, or double release.
  bool release(int index, std::uint32_t owner) {
    if (index < 0 || static_cast<std::size_t>(index) >= count_) return false;
    if (owner == 0 || owner_[index] != owner) return false;
    owner_[index] = 0;
    return true;
  }

  // Raw pointer to a slot for the registered owner; nullptr if not owned by `owner`.
  void* buffer(int index, std::uint32_t owner) {
    if (index < 0 || static_cast<std::size_t>(index) >= count_) return nullptr;
    if (owner_[index] != owner) return nullptr;
    return data_.data() + static_cast<std::size_t>(index) * slot_bytes_;
  }
  const void* buffer(int index, std::uint32_t owner) const {
    if (index < 0 || static_cast<std::size_t>(index) >= count_) return nullptr;
    if (owner_[index] != owner) return nullptr;
    return data_.data() + static_cast<std::size_t>(index) * slot_bytes_;
  }

  // Owner id of a slot (0 = free), or 0 on out-of-range.
  std::uint32_t owner(int index) const {
    if (index < 0 || static_cast<std::size_t>(index) >= count_) return 0;
    return owner_[index];
  }

 private:
  std::size_t count_ = 0;
  std::size_t slot_bytes_ = 0;
  std::vector<std::uint8_t> data_;
  std::vector<std::uint32_t> owner_;
};

}  // namespace m27

#endif  // M27_BUFFER_POOL_HPP
