# Ring Buffer Specification

Implement a fixed-size ring buffer (circular buffer) in C, targeting embedded systems.
Target standard: C99. MISRA C:2012 compliance required.

## Compile-Time Constants

- `RB_CAPACITY` — maximum number of elements; default value 16
- Element type: `uint8_t`

## Data Structure

```c
typedef struct {
    uint8_t data[RB_CAPACITY];
    uint8_t head;
    uint8_t tail;
    uint8_t count;
} RingBuffer;
```

All fields use fixed-width integer types from `<stdint.h>`. No dynamic memory.

## Status Codes

```c
typedef enum {
    RB_OK          = 0,
    RB_ERROR_FULL  = 1,
    RB_ERROR_EMPTY = 2
} RbStatus;
```

## API

### `void rb_init(RingBuffer *rb)`
Initialize the ring buffer to an empty state. Sets head, tail, and count to zero.

### `RbStatus rb_push(RingBuffer *rb, uint8_t value)`
Write one byte to the buffer.
- Returns `RB_OK` if the element was written successfully.
- Returns `RB_ERROR_FULL` if the buffer is already at capacity; the buffer is unchanged.

### `RbStatus rb_pop(RingBuffer *rb, uint8_t *out)`
Read and remove the oldest element from the buffer.
- Returns `RB_OK` and writes the value to `*out` on success.
- Returns `RB_ERROR_EMPTY` if the buffer is empty; `*out` is not written.

### `RbStatus rb_peek(const RingBuffer *rb, uint8_t *out)`
Read the oldest element without removing it.
- Returns `RB_OK` and writes the value to `*out` on success.
- Returns `RB_ERROR_EMPTY` if the buffer is empty; `*out` is not written.

### `uint8_t rb_count(const RingBuffer *rb)`
Return the number of elements currently stored in the buffer.

### `bool rb_is_full(const RingBuffer *rb)`
Return true if and only if `rb_count(rb) == RB_CAPACITY`.

### `bool rb_is_empty(const RingBuffer *rb)`
Return true if and only if `rb_count(rb) == 0`.

## Behavioral Constraints

- **No dynamic memory**: No malloc, calloc, realloc, or free.
- **No global mutable state**: All state is contained within the `RingBuffer` struct.
- **No recursion**.
- **No goto**.
- **Single return point per function**: Each function has exactly one return statement.
- **FIFO ordering**: The first element pushed is the first element popped.
- **Wrap-around**: The index wraps correctly using modulo `RB_CAPACITY`. The buffer
  continues to accept new elements after a full push/pop cycle.
- **Integer types**: All integer values where size matters use fixed-width types
  from `<stdint.h>` (`uint8_t`, `uint16_t`, etc.). Do not use bare `int` or `unsigned`.
- **Include guard**: The header file must use an include guard.
- **Headers included**: Include `<stdint.h>` and `<stdbool.h>` where required.
