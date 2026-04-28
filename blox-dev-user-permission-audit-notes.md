# Blox-Dev User Permission Audit Notes

Repository reviewed: `BloxSoftware/Blox-Dev`

Branch reviewed mainly: `development`

---

## Summary

The project has a model-level permission system using `UserPermission` flags:

```text
is_read
is_create
is_update
is_delete
```

The system exists, but permission enforcement is not fully consistent across all APIs.

Some APIs correctly check `is_update`, `is_create`, or `is_delete`, but some mutation APIs still check only `is_read` or do not check permission strongly enough.

---

## Main Permission Concepts

### 1. `user_type`

`user_type == 2` behaves like an admin bypass in backend permission checks.

If the user has `user_type == 2`, backend allows access without checking model-level `UserPermission` flags.

### 2. Organization role

The organization role comes from `role_id` and maps to roles like:

```text
owner
admin
planner
```

This is mostly used for organization/team-level actions.

### 3. Model-level permission

Model access is controlled through `UserPermission`.

A view-only user should usually have:

```text
is_read=true
is_create=false
is_update=false
is_delete=false
```

An edit user usually has:

```text
is_read=true
is_create=true
is_update=true
is_delete=true
```

---

## Issues / Fix Areas

## 1. Read-only users can share models

### Current issue

`ModelShare.post()` allows sharing if the user has only read permission.

Current check:

```python
check_model_permission(..., action='is_read')
```

This means a view-only user can still call:

```http
POST /model/<MODEL_ID>/share
```

and share the model.

### Recommended fix

Sharing should require stronger permission, preferably `is_delete` because sharing/access-management is similar to changing permissions.

```python
if not check_model_permission(user=current_user, model_id=model.id, action='is_delete'):
    return unauthorized()
```

If the product wants editors to share but not only owners, then use `is_update` instead.

---

## 2. New model-share invite route also needs stronger permission

### Current issue

If the new invite flow exists, `ModelShareInvite.post()` should not allow view-only users to send invites.

If it checks only:

```python
check_model_permission(..., action='is_read')
```

then view-only users can invite others.

### Recommended fix

Use:

```python
if not check_model_permission(user=current_user, model_id=model.id, action='is_delete'):
    return unauthorized()
```

or `is_update` depending on desired product rule.

---

## 3. Changing a user to `view` does not clear `is_delete`

### Current issue

When model access is changed to `view`, the code clears:

```python
is_update = False
is_create = False
```

but does not always clear:

```python
is_delete = False
```

### Why this is dangerous

If the user was previously an editor/owner and had `is_delete=true`, then after changing them to view, `is_delete` may remain true.

So the UI may show them as `view`, but backend may still allow some powerful actions.

### Recommended fix

When role is changed to `view`, set all non-read permissions to false:

```python
elif role == "view":
    user_perm.is_read = True
    user_perm.is_update = False
    user_perm.is_create = False
    user_perm.is_delete = False
```

---

## 4. `UserModelPermission.post()` has no permission check

### Current issue

The endpoint that creates a `UserPermission` row can create permission directly without checking whether the current user is allowed to grant access.

### Risk

An authenticated user who knows `model_id` and `user_id` may be able to create permission rows.

### Recommended fix

Before creating permission, check that the current user can manage permissions for that model:

```python
if not check_model_permission(current_user, data["model_id"], action="is_delete"):
    return unauthorized()
```

---

## 5. Block creation checks `is_read` instead of `is_create`

### Current issue

Creating a block is a mutation action, but the API checks read permission.

That means a read-only user may be able to create blocks.

### Recommended fix

Use `is_create`:

```python
if not check_model_permission(user=current_user, model_id=model.id, action='is_create'):
    return unauthorized()
```

---

## 6. Organization update should require owner/admin role

### Current issue

The organization update API allows authenticated users to update organization details.

This can include fields like:

```text
company
unique_name
industry
website
logo_url
```

### Simple explanation

This is not a model-level action. It is an organization-level action.

So it should not depend on model permission like `is_update` or `is_delete`.

It should depend on organization role.

Only these roles should usually update organization settings:

```text
owner
admin
```

A normal planner/member should not be able to update organization-level settings.

### Recommended fix

At the start of the organization update API, add:

```python
if current_user.role.role not in ["owner", "admin"]:
    return {"message": "Permission Denied"}, 401
```

---

## 7. Org/team role comparison uses `role_id` ordering

### Current issue

Some org/team role checks compare role IDs like this:

```python
if current_user.role_id > user_to_modify.role.id or current_user.role_id > role.id:
    return {"message": "Permission denied"}, 404
```

### What this means in simple English

The code assumes role IDs are ordered by power.

Example assumption:

```text
owner   = 1
admin   = 2
planner = 3
```

With this assumption:

```text
smaller role_id = more powerful role
larger role_id = less powerful role
```

So the code says:

```text
If current user's role_id is greater than the target role_id,
then current user is weaker and should not be allowed.
```

### Why this is risky

This works only if role IDs always stay in the correct order.

If database seed data changes, or roles are inserted differently, the logic may break.

For example, if IDs become:

```text
owner   = 3
admin   = 1
planner = 2
```

then the permission check becomes wrong.

### Better approach

Use explicit role priority instead of relying on database IDs:

```python
role_priority = {
    "owner": 1,
    "admin": 2,
    "planner": 3,
}

current_priority = role_priority[current_user.role.role]
target_priority = role_priority[user_to_modify.role.role]
new_role_priority = role_priority[role.role]

if current_priority > target_priority or current_priority > new_role_priority:
    return {"message": "Permission denied"}, 403
```

This is clearer and safer because role power is defined in code, not guessed from DB IDs.

---

## 8. `ModelLink.get()` may allow read-only users to generate access links

### Current issue

`ModelLink.get()` checks only read permission before returning a shareable model link.

Current style:

```python
check_model_permission(..., action='is_read')
```

### Why this may be a problem

If the generated link can later be used by another user to gain model access through `/model/access`, then this is not just a view action.

It becomes an access-granting action.

In that case, read-only users should not be able to generate that link.

### Recommended rule

If the link only lets the current user open the model, `is_read` is okay.

If the link can grant access to another user, use stronger permission:

```python
if not check_model_permission(user=current_user, model_id=model.id, action='is_delete'):
    return unauthorized()
```

or `is_update`, depending on product decision.

---

## Final Priority List

Recommended order of fixes:

1. Change model share permission from `is_read` to `is_delete` or `is_update`.
2. Change model-share invite permission from `is_read` to `is_delete` or `is_update`.
3. Clear `is_delete=False` when changing a user to `view`.
4. Add permission check to `UserModelPermission.post()`.
5. Change block creation permission check from `is_read` to `is_create`.
6. Restrict organization update to owner/admin.
7. Replace `role_id` ordering checks with explicit role priority mapping.
8. Review `ModelLink.get()` and require stronger permission if the link grants access.

---

## Simple Final Summary

The permission system exists, but some APIs use the wrong permission level.

Read-only users should only view data, but currently some routes may still allow them to share models, create blocks, or trigger access-related actions.

The main backend fix is to ensure every state-changing API checks the correct permission flag.
