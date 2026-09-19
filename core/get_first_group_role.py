from discord.member import Member
from discord.role import Role
from discord.user import User

from core.config import cfg


def get_first_group_role(user: User | Member) -> Role | None:
    roles: list[Role] = user.roles  # pyright: ignore[reportAttributeAccessIssue]

    for role in roles:
        if role.id in cfg.GROUPS_CONFIG.role_id_to_number:
            return role

    return None
