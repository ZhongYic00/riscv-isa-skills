from rr_spike_rv_replay.isa_events import classify_isa_event, extract_isa_events
from rr_spike_rv_replay.trace_bridge import TraceRecord


def test_classify_isa_event_detects_csr_read_write_and_trap() -> None:
    assert classify_isa_event("csrr a5, mstatus") == "csr-read"
    assert classify_isa_event("csrw mstatus, a5") == "csr-write"
    assert classify_isa_event("csrrw sp, sscratch, sp") == "csr-read-write"
    assert classify_isa_event("ecall") == "trap"
    assert classify_isa_event("ebreak") == "trap"


def test_extract_isa_events_filters_around_target_window() -> None:
    records = [
        TraceRecord(index=8, pc="0x8008", text="addi a0, a0, 1", hart_id=0),
        TraceRecord(index=9, pc="0x8009", text="csrr a5, mstatus", hart_id=0),
        TraceRecord(index=10, pc="0x8010", text="csrw mstatus, a5", hart_id=0),
        TraceRecord(index=11, pc="0x8011", text="ecall", hart_id=0),
        TraceRecord(index=12, pc="0x8012", text="addi a1, a1, 1", hart_id=0),
    ]

    events = extract_isa_events(records, target_index=10, before=1, after=1, hart_id=0)

    assert [event["index"] for event in events] == [9, 10, 11]
    assert [event["event_type"] for event in events] == ["csr-read", "csr-write", "trap"]


def test_extract_isa_events_marks_target_record() -> None:
    records = [
        TraceRecord(index=20, pc="0x9000", text="csrr a0, fflags", hart_id=0),
    ]

    events = extract_isa_events(records, target_index=20, before=0, after=0, hart_id=0)

    assert events[0]["is_target"] is True
