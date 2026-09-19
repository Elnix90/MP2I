"""A dictionry that associate a group number to a discord role id.

The bot uses them to determinate the group in which the user that requests the command is.
"""

ROLES_IDS: dict[int, int] = {
    1: 1547629723239059486,
    2: 1547630075762049024,
    3: 1547630246566568056,
    4: 1547630387260563578,
    5: 1547630555825184798,
    6: 1547630810478280815,
    7: 1547631016783519914,
    8: 1547631181732778034,
    9: 1547631314822504468,
    10: 1547631419537358928,
    11: 1547631567634038846,
    12: 1547631772806946857,
    13: 1547631889274118275,
    14: 1547631955615420416,
}

ROLE_ID_TO_NUMBER: dict[int, int] = {role_id: n for n, role_id in ROLES_IDS.items()}
