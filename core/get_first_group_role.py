from discord.member import Member
from discord.role import Role
from discord.user import User

from core.roles_ids import ROLES_IDS


def get_first_group_role(user: User | Member) -> Role | None:
    roles: list[Role] = user.roles  # pyright: ignore[reportAttributeAccessIssue]

    for role in roles:
        if role.id in ROLES_IDS.values():
            return role

    return None
