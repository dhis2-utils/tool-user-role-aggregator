# User Role Aggregator Tool - User Manual

## Introduction

The User Role Aggregator Tool helps administrators work with DHIS2 user roles. Any user who can open the app can check what a combination of roles is able to administer; looking up another user to see the same thing additionally requires the authority to view users. Users who may manage user roles themselves get two further sections to create a new user admin role or extend an existing one.

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Usage](#usage)
    - [Check Access: Role Combination](#check-access-role-combination)
    - [Check Access: Look Up a User](#check-access-look-up-a-user)
    - [Create New User Role for User Admins](#create-new-user-role-for-user-admins)
    - [Validate or Update Existing User Admin Role](#validate-or-update-existing-user-admin-role)
4. [Feedback and Notifications](#feedback-and-notifications)
5. [Testing](#testing)
6. [Reporting Issues](#reporting-issues)

## Requirements

- DHIS2 instance (with appropriate user privileges)
- Administrative access to the DHIS2 instance to install the web app

## Installation

### Downloading the App

1. **Go to GitHub Repository:**

    Navigate to the [GitHub repository](https://github.com/dhis2/tool-user-role-aggregator/releases) where the release of the app is available.

2. **Download the .zip File:**

    Locate the latest release and download the `.zip` file containing the app.

### Installing the App in DHIS2

1. **Login to DHIS2:**

    Login to your DHIS2 instance with administrative credentials.

2. **Access the App Management Module:**

    Navigate to the "App Management" module from the DHIS2 dashboard.

3. **Upload the .zip File:**
    - Click on the "Install from file" button.
    - Select the downloaded `.zip` file and upload it.

4. **Verify Installation:**

    After the upload completes, verify that the "User Role Aggregator App" appears in the list of installed apps.

**Warning**: Do not install this app directly in a production environment without thorough testing. Always test in a development or staging environment first to ensure all functionalities work as expected.

## Usage

The sidebar has two groups. "Check access" is read-only and visible to everyone; it never changes any data. "Manage roles" — Create new role and Update existing role — only appears for users who hold "Add/Update Public User Role" or "Add/Update Private User Role" (or the `ALL` authority). Users without one of those authorities do not see the group in the sidebar at all, and opening `#/create` or `#/update` directly shows a "Missing permissions" message instead of the form.

### Check Access: Role Combination

This is the landing page of the app (`#/`), reached by default or via "Role combination" under "Check access" in the sidebar.

1. **Select the roles a user holds:**

    Use the "User roles held" transfer widget to pick one or more roles. Roles that themselves carry a user-administration authority are badged "user admin" and sorted to the top, so they are easy to find. Your selection is reflected in the page's `?roles=` URL parameter, so a particular check can be bookmarked or shared with a link.

2. **Read the report:**

    The roles' authorities are combined, because a user administers other users with everything their roles grant together, not with one role at a time. The report shows how many roles and authorities were combined, then one of:
    - **Cannot administer users** — none of the selected roles grants an authority for administering users, so the combination cannot manage any users at all, regardless of its other authorities. Nothing further is listed in this case.
    - **Can administer users, via `<authority>`** — followed by a **Can manage** list of user roles the combination can administer, and a **Cannot manage** list of the roles it cannot, each with the specific authorities missing to manage that role.

    If the authority that grants administration is "Add/Update User Within Managed Group", the report additionally shows a "Limited to managed user groups" notice. This is where the tool's limitation applies:

    > The tool evaluates authorities only. If a role's user-administration authority is "Add/Update User Within Managed Group", whether a particular user can be administered also depends on user-group management, which this tool does not evaluate.

### Check Access: Look Up a User

Reached via "Look up user" under "Check access" in the sidebar. This item — and the `#/check-user` page itself — is only visible to users holding the `F_USER_VIEW` authority (or `ALL`); without it, the nav item is hidden.

1. **Search for a user:**

    Type at least two characters of a name or username into the search field. Matching users appear in a list below as you type.

2. **Select a user:**

    Click a user in the results to select them.

3. **Read the report:**

    The tool shows the roles the selected user holds and reports what their combined authorities can and cannot manage, exactly as described above for a role combination — including the same "Cannot administer users" outcome, the same "Can manage" / "Cannot manage" lists with missing authorities, and the same managed-user-group limitation:

    > The tool evaluates authorities only. If a role's user-administration authority is "Add/Update User Within Managed Group", whether a particular user can be administered also depends on user-group management, which this tool does not evaluate.

### Create New User Role for User Admins

Visible only to users holding "Add/Update Public User Role" or "Add/Update Private User Role" (or `ALL`).

1. **Navigate to "Create new role":**

    Click on "Create new role" in the sidebar to open the interface for creating a new user admin role.

2. **Enter Role Name:**

    Enter a name for the new role in the "Role name" input field.

3. **Select User Roles to Manage:**

    Use the "User roles to manage" transfer widget to select one or more user roles that the new admin role should be able to manage. The widget has a filter field to help find roles quickly. Only roles you are yourself allowed to manage are listed.

4. **Select Additional Authorities:**

    Use the "Additional authorities" transfer widget to add additional authorities for the new role. The authorities related to user management are pre-selected, but can be deselected.

    Only authorities you hold yourself are listed: the tool will not let you create a role more privileged than your own account. Superusers (users with the `ALL` authority) see every authority.

    If the roles and authorities selected so far would not let the new role administer any users at all, a "This role cannot administer users" warning appears before you submit, so you can add a role or authority that grants user administration if that was not intended.

5. **Create Role:**

    Click on the "Create role" button to create the new user admin role. You will receive a success or error message based on the outcome.

### Validate or Update Existing User Admin Role

Visible only to users holding "Add/Update Public User Role" or "Add/Update Private User Role" (or `ALL`).

1. **Navigate to "Update existing role":**

    Click on "Update existing role" in the sidebar to open the interface for updating an existing user admin role.

2. **Select Existing Role:**

    Use the "Existing role" dropdown to select the role that you want to inspect or update. This page no longer shows its own list of what the role can manage; instead, click the "Check what this role can manage" link that appears once a role is selected to open the Check Access page pre-filled with that role.

3. **Add Managed Roles:**

    Use the "Add managed roles" transfer widget to pick additional roles that the selected role should be able to manage. Only roles whose authorities you hold yourself are listed, for the same reason as above — so if the list is empty, it means there are no further roles you are allowed to add, not that the role already manages everything.

4. **Save:**

    Click on the "Add authorities to role" button to save the changes. The authorities of the picked roles are added to the selected role. You will receive a success or error message based on the outcome.

## Feedback and Notifications

Feedback is provided through alert bars that appear at the bottom of the app. These messages inform the user about the success or failure of their actions:

- **Success**: Green alert message.
- **Error**: Red alert message with error details.

## Testing

It is crucial to test this app thoroughly in a development or staging environment before deploying it to a production instance. This ensures that all functionalities work as expected and helps identify and fix any potential issues.

### Steps for Testing:

1. **Setup Development Environment:**

    Ensure you have a DHIS2 development or staging instance set up and configured with necessary permissions, using a fresh copy of the production environment.

2. **Test User Role Creation:**
    - Try creating a new user admin role.
    - Verify that the role appears in the DHIS2 instance.
    - Check if the role has the expected authorities and can manage the specified roles.

3. **Test User Role Update:**
    - Select an existing user admin role and use its "Check what this role can manage" link to see what it currently manages.
    - Add managed roles and save.
    - Verify that the changes reflect in the DHIS2 instance.

4. **Edge Cases:**
    - Test with missing or incorrect input data.
    - Verify error handling and feedback mechanisms.

## Reporting Issues:

If you encounter any issues not covered in this manual, please report them to the development team with detailed descriptions and steps to reproduce the problem.
