"""Callback-данные кнопок.

Все шаги записи передают выбор клиента прямо в callback_data,
поэтому бот не теряет контекст даже после перезапуска.
"""
from aiogram.filters.callback_data import CallbackData


class MenuCb(CallbackData, prefix="menu"):
    action: str  # main | book | my | services | contacts


class ServiceCb(CallbackData, prefix="svc"):
    service_id: int


class MasterCb(CallbackData, prefix="mst"):
    service_id: int
    master_id: int


class DayCb(CallbackData, prefix="day"):
    service_id: int
    master_id: int
    day: str  # YYYYMMDD


class TimeCb(CallbackData, prefix="tm"):
    service_id: int
    master_id: int
    day: str
    minutes: int


class ConfirmCb(CallbackData, prefix="ok"):
    service_id: int
    master_id: int
    day: str
    minutes: int


class CancelCb(CallbackData, prefix="cnl"):
    appointment_id: int
    action: str  # ask | yes


class NoopCb(CallbackData, prefix="noop"):
    reason: str = ""  # past | full | ""


class AdminCb(CallbackData, prefix="adm"):
    action: str  # panel | day | cal | manage | toggle_day | toggle_slot
    day: str = ""
    minutes: int = -1
