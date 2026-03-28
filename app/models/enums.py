from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AssetState(StrEnum):
    N_O = "n_o"
    ON_BALANCE = "on_balance"
    OFF_BALANCE = "off_balance"
    WRITTEN_OFF = "written_off"


class EventStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class EventItemKind(StrEnum):
    OBJECT = "object"
    GROUP = "group"


class ValuationKind(StrEnum):
    ACCOUNTING = "accounting"
    ASSESSMENT_ACT = "assessment_act"
    PRICE_LIST = "price_list"
    INITIAL_VALUE_ACT = "initial_value_act"
    RESIDUAL_VALUE_STATEMENT = "residual_value_statement"
