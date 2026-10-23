# User Admin Role Aggregator { #tool-user-role-aggregator-guide }

## What the tool is for { #tool-user-role-aggregator-about }

The User Admin Role Aggregator shows which user roles a user administrator can manage, and creates or extends roles for user administrators. It is for system administrators who set up user management in DHIS2.

In DHIS2, a user can manage another user only when they hold every authority of that user's roles. A user administrator with the `ALL` authority can manage everybody. The tool applies this rule to a combination of roles, or to a user, and lists what they can and cannot manage. It can also build a role that holds all the authorities of the roles that an administrator must manage.

## Before you start { #tool-user-role-aggregator-before-you-start }

The tool runs on DHIS2 2.40 and later.

Which parts of the tool you see depends on your authorities:

| Part of the tool                                 | Authority you need                                                  |
| ------------------------------------------------ | ------------------------------------------------------------------- |
| **Role combination**                             | Access to the app                                                   |
| **Look up user**                                 | **View User** (`F_USER_VIEW`)                                       |
| **Create new role** and **Update existing role** | **Add/Update Public User Role** or **Add/Update Private User Role** |

A user with the `ALL` authority sees every part.

> **Warning**
>
> **Create new role** and **Update existing role** change user roles, and the change affects every user who holds the role. Try the tool on a copy of your database first.

## Install the tool { #tool-user-role-aggregator-install }

The tool is not on the App Hub. Install it from its GitHub release, or from the tool-box app.

To install it from the GitHub release:

1. Open the [releases page](https://github.com/dhis2-utils/tool-user-role-aggregator/releases) of the tool.
2. Download the `.zip` file of the newest release.
3. In the **App Management** app, click **Upload app**, and choose the `.zip` file.

<!-- VERIFY IN APP: the upload label in App Management on 2.40, 2.41, 2.42 and 2.43. -->

The app appears in the DHIS2 menu as **User Admin Role Aggregator**.

To let other users open the app, add the app to their user role in the **Users** app.

## Check what a role combination can manage { #tool-user-role-aggregator-check-roles }

A user administers other users with the authorities of all their roles together. Use this check to see what a set of roles can manage before you give them to someone. The check does not change any data.

1. In the sidebar, under **Check access**, click **Role combination**.
2. In **User roles held**, choose the roles. Roles that give user administration have the tag **user admin**.

The report shows how many roles and authorities were combined, and then one of these results:

- **Cannot administer users**: none of the roles gives an authority to administer users. The combination cannot manage anybody, whatever its other authorities are.
- **Can administer users, via** an authority: a **Can manage** list with the roles that the combination can manage, and a **Cannot manage** list with the other roles. For each role in **Cannot manage**, the report shows the authorities that are missing.

The roles you choose are saved in the page address, so you can bookmark a check or send it as a link.

## Look up what a user can manage { #tool-user-role-aggregator-check-user }

Use this check to see what an existing user can manage with the roles they hold. The check does not change any data.

1. In the sidebar, under **Check access**, click **Look up user**.
2. In **Search by name or username**, enter at least two characters of the name or username.
3. Click the user in the list of results.

The tool shows the roles that the user holds, and the same report as for a role combination. The search shows the first 10 users that match. If more users match, the tool says so, and you can enter more of the name.

## Create a role for a user administrator { #tool-user-role-aggregator-create }

Use this task to create a new role that can manage a set of other roles. The new role gets all the authorities of the roles that you choose.

> **Warning**
>
> The new role can do everything that the chosen roles can do. Give it only to users who should have all those authorities.

1. In the sidebar, under **Manage roles**, click **Create new role**.
2. In **Role name**, enter a name for the role.
3. In **User roles to manage**, choose the roles that the new role must be able to manage.
4. Optional: in **Additional authorities**, add or remove authorities. The authorities for user management are already chosen.
5. Click **Create role**.

The message **User role created successfully** appears. The role description lists the roles that the new role manages.

If the chosen roles and authorities do not let the role administer users, the warning **This role cannot administer users** appears before you click **Create role**.

The tool lists only the roles and authorities that you hold yourself, so you cannot create a role with more authorities than your own account. If a chosen role gets an authority that you do not hold before you click **Create role**, the tool does not create the role and says which authorities are the problem.

## Add managed roles to an existing role { #tool-user-role-aggregator-update }

Use this task when a user administrator must manage more roles than before. The tool adds the authorities of the roles that you choose to an existing role.

> **Warning**
>
> The change affects every user who holds the existing role.

1. In the sidebar, under **Manage roles**, click **Update existing role**.
2. In **Existing role**, choose the role to change.
3. In **Add managed roles**, choose the roles that the existing role must also be able to manage.
4. Click **Add authorities to role**.

The message **User role updated successfully** appears.

To see what the existing role can manage now, click **Check what this role can manage**. The role combination check opens with the role chosen.

**Add managed roles** lists only roles whose authorities you hold yourself. An empty list means that there are no further roles that you can add. It does not mean that the role already manages every role.

## Known limitations { #tool-user-role-aggregator-limitations }

- The tool checks authorities only. A role with **Add/Update User Within Managed Group** (`F_USER_ADD_WITHIN_MANAGED_GROUP`) can manage a user only in the user groups that it manages. The tool does not check user groups, and shows the notice **Limited to managed user groups** instead.
- The tool checks only the roles that you can see. If roles are not shared with you, they are not in the report, and **All user roles can be managed** can be wrong for those roles.
- The tool does not remove authorities from a role. To remove an authority, use the **Users** app.
- **Update existing role** reads the role and then saves it. If another administrator changes the same role at the same moment, one of the two changes can be lost.
- The tool updates its list of roles at most once a minute. If roles are changed in another app, the report can be up to one minute old. Refresh the page to see the change at once.
- A role created by the tool belongs to your user account. In DHIS2, you cannot delete a user account while it is the creator of a role.
