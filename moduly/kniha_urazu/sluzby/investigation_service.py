from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
from moduly.kniha_urazu.repository.investigation_repository import InvestigationRepository


class InvestigationService:
    def __init__(self):
        self.repository = InvestigationRepository()

    def get_or_create(self, accident_id: int) -> AccidentInvestigation:
        investigation = self.repository.get_by_accident_id(accident_id)
        if investigation is not None:
            return investigation
        return AccidentInvestigation(accident_id=accident_id)

    def save_oznameni(self, accident_id: int, **data) -> AccidentInvestigation:
        investigation = self.get_or_create(accident_id)

        for key, value in data.items():
            if hasattr(investigation, key):
                setattr(investigation, key, value)

        return self.repository.save(investigation)

    def save_zajisteni_dukazu(self, accident_id: int, data_json: str) -> AccidentInvestigation:
        investigation = self.get_or_create(accident_id)
        investigation.zajisteni_dukazu_json = data_json
        return self.repository.save(investigation)


investigation_service = InvestigationService()
