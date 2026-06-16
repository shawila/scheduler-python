from datetime import datetime
import pytest
from app.slots import compute_free_slots

DATE = datetime(2024, 8, 1)


def busy(start_hhmm, end_hhmm):
    return {
        'start': f'2024-08-01T{start_hhmm}:00Z',
        'end':   f'2024-08-01T{end_hhmm}:00Z',
    }


class TestComputeFreeSlots:
    def test_no_busy_times_returns_all_47_slots(self):
        slots = compute_free_slots([], DATE)
        assert len(slots) == 47

    def test_entire_day_busy_returns_empty(self):
        slots = compute_free_slots([busy('00:00', '23:59')], DATE)
        assert slots == []

    def test_one_slot_busy_excludes_only_that_slot(self):
        slots = compute_free_slots([busy('09:00', '09:30')], DATE)
        assert '09:00 - 09:30' not in slots
        assert len(slots) == 46

    def test_busy_spanning_slot_boundary_excludes_both_slots(self):
        # 09:15–09:45 overlaps both 09:00–09:30 and 09:30–10:00
        slots = compute_free_slots([busy('09:15', '09:45')], DATE)
        assert '09:00 - 09:30' not in slots
        assert '09:30 - 10:00' not in slots
        assert len(slots) == 45

    def test_busy_ending_exactly_at_slot_start_does_not_block_that_slot(self):
        # busy 08:30–09:00 must NOT block the 09:00–09:30 slot
        slots = compute_free_slots([busy('08:30', '09:00')], DATE)
        assert '08:30 - 09:00' not in slots
        assert '09:00 - 09:30' in slots

    def test_busy_starting_exactly_at_slot_end_does_not_block_previous_slot(self):
        # busy 09:30–10:00 must NOT block the 09:00–09:30 slot
        slots = compute_free_slots([busy('09:30', '10:00')], DATE)
        assert '09:00 - 09:30' in slots
        assert '09:30 - 10:00' not in slots

    def test_back_to_back_busy_periods_block_all_covered_slots(self):
        slots = compute_free_slots(
            [busy('09:00', '10:00'), busy('10:00', '11:00')], DATE
        )
        for blocked in ['09:00 - 09:30', '09:30 - 10:00', '10:00 - 10:30', '10:30 - 11:00']:
            assert blocked not in slots

    def test_slot_format_is_hhmm_dash_hhmm(self):
        slots = compute_free_slots([], DATE)
        assert slots[0] == '00:00 - 00:30'
        assert slots[-1] == '23:00 - 23:30'
