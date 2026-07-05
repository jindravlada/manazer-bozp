from dataclasses import dataclass, field

from moduly.kontroly.modely.thp_monthly_control import ThpMonthlyControl
from moduly.kontroly.modely.thp_yearly_kl_usage import ThpYearlyKlUsage
from moduly.kontroly.repository.monthly_control_repository import MonthlyControlRepository
from moduly.kontroly.repository.yearly_kl_repository import YearlyKlRepository
from moduly.nastaveni.sluzby.settings_service import settings_service


@dataclass(frozen=True)
class MonthCell:
    status: str = "none"


@dataclass
class ThpYearRow:
    thp_worker_id: int
    thp_worker_name: str
    months: dict[int, MonthCell] = field(default_factory=dict)
    kl_flags: dict[int, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class YearMatrixSummary:
    thp_count: int = 0
    done_count: int = 0
    defect_count: int = 0
    none_count: int = 0
    excused_count: int = 0


@dataclass(frozen=True)
class YearMatrixMonthSummary:
    done_by_month: tuple[int, ...] = (0,) * 12
    defect_by_month: tuple[int, ...] = (0,) * 12
    none_by_month: tuple[int, ...] = (0,) * 12
    excused_by_month: tuple[int, ...] = (0,) * 12


@dataclass(frozen=True)
class YearMatrixKlSummary:
    completed_kl_count: int = 0
    missing_kl_numbers: tuple[int, ...] = ()


class MonthlyControlService:
    VALID_STATUSES = {"none", "ok", "defect", "excused"}
    STATUS_CYCLE = ("none", "ok", "defect", "excused")

    def __init__(self):
        self.repository = MonthlyControlRepository()
        self.kl_repository = YearlyKlRepository()

    def get_year_matrix(self, year: int) -> list[ThpYearRow]:
        workers = settings_service.get_workers_for_controls()
        monthly_records = self.repository.get_by_year(year)
        kl_records = self.kl_repository.get_by_year(year)

        monthly_by_key = {
            (record.thp_worker_id, record.month): record for record in monthly_records
        }
        kl_by_worker = {record.thp_worker_id: record for record in kl_records}

        rows: list[ThpYearRow] = []
        for worker in workers:
            months: dict[int, MonthCell] = {}
            for month in range(1, 13):
                record = monthly_by_key.get((worker.id, month))
                if record is None:
                    months[month] = MonthCell()
                    continue

                status = record.status if record.status in self.VALID_STATUSES else "none"
                months[month] = MonthCell(status=status)

            kl_record = kl_by_worker.get(worker.id)
            kl_flags = kl_record.kl_flags() if kl_record is not None else {index: False for index in range(1, 13)}

            rows.append(
                ThpYearRow(
                    thp_worker_id=worker.id,
                    thp_worker_name=worker.display_name,
                    months=months,
                    kl_flags=kl_flags,
                )
            )

        return rows

    def compute_summary(self, rows: list[ThpYearRow]) -> YearMatrixSummary:
        none_count = 0
        done_count = 0
        defect_count = 0
        excused_count = 0

        for row in rows:
            for month in range(1, 13):
                cell = row.months.get(month)
                status = cell.status if cell is not None else "none"
                if status == "ok":
                    done_count += 1
                elif status == "defect":
                    done_count += 1
                    defect_count += 1
                elif status == "excused":
                    excused_count += 1
                else:
                    none_count += 1

        return YearMatrixSummary(
            thp_count=len(rows),
            done_count=done_count,
            defect_count=defect_count,
            none_count=none_count,
            excused_count=excused_count,
        )

    def compute_monthly_summary(self, rows: list[ThpYearRow]) -> YearMatrixMonthSummary:
        done_by_month = [0] * 12
        defect_by_month = [0] * 12
        none_by_month = [0] * 12
        excused_by_month = [0] * 12

        for row in rows:
            for month in range(1, 13):
                cell = row.months.get(month)
                status = cell.status if cell is not None else "none"
                index = month - 1
                if status == "defect":
                    defect_by_month[index] += 1
                    done_by_month[index] += 1
                elif status == "ok":
                    done_by_month[index] += 1
                elif status == "excused":
                    excused_by_month[index] += 1
                else:
                    none_by_month[index] += 1

        return YearMatrixMonthSummary(
            done_by_month=tuple(done_by_month),
            defect_by_month=tuple(defect_by_month),
            none_by_month=tuple(none_by_month),
            excused_by_month=tuple(excused_by_month),
        )

    def compute_kl_summary(self, rows: list[ThpYearRow]) -> YearMatrixKlSummary:
        if not rows:
            return YearMatrixKlSummary(0, tuple(range(1, 13)))

        missing_kl_numbers: list[int] = []
        completed_kl_count = 0

        for kl_index in range(1, 13):
            if all(row.kl_flags.get(kl_index, False) for row in rows):
                completed_kl_count += 1
            else:
                missing_kl_numbers.append(kl_index)

        return YearMatrixKlSummary(
            completed_kl_count=completed_kl_count,
            missing_kl_numbers=tuple(missing_kl_numbers),
        )

    def cycle_status(self, year: int, month: int, thp_worker_id: int) -> MonthCell:
        record = self._ensure_monthly_record(year, month, thp_worker_id)
        current = record.status if record.status in self.VALID_STATUSES else "none"
        index = self.STATUS_CYCLE.index(current)
        record.status = self.STATUS_CYCLE[(index + 1) % len(self.STATUS_CYCLE)]
        saved = self.repository.save(record)
        return MonthCell(status=saved.status)

    def toggle_kl(self, year: int, thp_worker_id: int, kl_index: int) -> bool:
        record = self._ensure_kl_record(year, thp_worker_id)
        new_value = not record.get_kl_used(kl_index)
        record.set_kl_used(kl_index, new_value)
        saved = self.kl_repository.save(record)
        return saved.get_kl_used(kl_index)

    def _ensure_monthly_record(self, year: int, month: int, thp_worker_id: int) -> ThpMonthlyControl:
        record = self.repository.get_by_key(year, month, thp_worker_id)
        if record is not None:
            record.thp_worker_name = self._worker_name(thp_worker_id)
            return record

        return ThpMonthlyControl(
            year=year,
            month=month,
            thp_worker_id=thp_worker_id,
            thp_worker_name=self._worker_name(thp_worker_id),
            status="none",
        )

    def _ensure_kl_record(self, year: int, thp_worker_id: int) -> ThpYearlyKlUsage:
        record = self.kl_repository.get_by_key(year, thp_worker_id)
        if record is not None:
            record.thp_worker_name = self._worker_name(thp_worker_id)
            return record

        return ThpYearlyKlUsage(
            year=year,
            thp_worker_id=thp_worker_id,
            thp_worker_name=self._worker_name(thp_worker_id),
        )

    def _worker_name(self, thp_worker_id: int) -> str:
        worker = settings_service.get_worker_by_id(thp_worker_id)
        return worker.display_name if worker else ""


monthly_control_service = MonthlyControlService()
