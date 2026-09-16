from discord.member import Member
from discord.user import User

_ADMIN_iDS = [1416319211495755898, 1123534156626939945]


def is_admin(user: User | Member) -> bool:
    return user.id in _ADMIN_iDS
