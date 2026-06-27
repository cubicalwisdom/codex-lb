from __future__ import annotations

import pytest

from app.core.utils.time import utcnow
from app.db.models import Account, AccountStatus, UsageHistory
from app.db.session import SessionLocal
from app.modules.accounts.repository import AccountsRepository
from app.modules.usage.repository import UsageRepository


def _account(
    account_id: str = "acc_refresh",
    *,
    chatgpt_account_id: str = "chatgpt_refresh",
    email: str | None = None,
    workspace_id: str | None = None,
    workspace_label: str | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> Account:
    return Account(
        id=account_id,
        chatgpt_account_id=chatgpt_account_id,
        email=email or f"{account_id}@example.com",
        workspace_id=workspace_id,
        workspace_label=workspace_label,
        plan_type="plus",
        access_token_encrypted=b"access",
        refresh_token_encrypted=b"refresh",
        id_token_encrypted=b"id",
        last_refresh=utcnow(),
        status=status,
        deactivation_reason=None,
        limit_warmup_enabled=True,
    )


@pytest.mark.asyncio
async def test_list_accounts_refresh_existing_reloads_identity_map(db_setup):
    del db_setup
    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert(_account())

    async with SessionLocal() as reader_session:
        reader_repo = AccountsRepository(reader_session)
        loaded = (await reader_repo.list_accounts())[0]
        assert loaded.limit_warmup_enabled is True
        await reader_session.commit()

        async with SessionLocal() as writer_session:
            writer_repo = AccountsRepository(writer_session)
            assert await writer_repo.update_limit_warmup_enabled("acc_refresh", False) is True

        stale = (await reader_repo.list_accounts())[0]
        assert stale is loaded
        assert stale.limit_warmup_enabled is True

        refreshed = (await reader_repo.list_accounts(refresh_existing=True))[0]
        assert refreshed is loaded
        assert refreshed.limit_warmup_enabled is False


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_user_paused_status_on_auth_sync(db_setup):
    del db_setup
    paused = _account(
        "acc_paused_persist",
        chatgpt_account_id="chatgpt_paused_persist",
        email="paused-persist@example.com",
        status=AccountStatus.PAUSED,
    )
    incoming_auth_sync = _account(
        "acc_paused_persist",
        chatgpt_account_id="chatgpt_paused_persist",
        email="paused-persist@example.com",
        status=AccountStatus.ACTIVE,
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert_account_slot(paused, preserve_unknown_workspace_duplicates=False)

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert_account_slot(incoming_auth_sync, preserve_unknown_workspace_duplicates=False)

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        loaded = await repo.get_by_id("acc_paused_persist")

    assert loaded is not None
    assert loaded.status == AccountStatus.PAUSED
    assert loaded.deactivation_reason is None
    assert loaded.reset_at is None
    assert loaded.blocked_at is None


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_emails_sharing_workspace_identity(db_setup):
    del db_setup
    shared_chatgpt_id = "chatgpt_workspace_shared"
    shared_workspace_id = "workspace_shared"
    first = _account(
        "first_slot",
        chatgpt_account_id=shared_chatgpt_id,
        email="first@example.com",
        workspace_id=shared_workspace_id,
    )
    second = _account(
        "second_slot",
        chatgpt_account_id=shared_chatgpt_id,
        email="second@example.com",
        workspace_id=shared_workspace_id,
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)

        assert saved_first.id == "first_slot"
        assert saved_second.id == "second_slot"
        accounts = await repo.list_accounts()

    assert [(account.id, account.email) for account in accounts] == [
        ("first_slot", "first@example.com"),
        ("second_slot", "second@example.com"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_emails_sharing_workspace_less_identity(db_setup):
    del db_setup
    shared_chatgpt_id = "chatgpt_workspace_less_shared"
    first = _account(
        "workspace_less_first",
        chatgpt_account_id=shared_chatgpt_id,
        email="first@example.com",
    )
    second = _account(
        "workspace_less_second",
        chatgpt_account_id=shared_chatgpt_id,
        email="second@example.com",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)

        assert saved_first.id == "workspace_less_first"
        assert saved_second.id == "workspace_less_second"
        accounts = await repo.list_accounts()

    assert [(account.id, account.email) for account in accounts] == [
        ("workspace_less_first", "first@example.com"),
        ("workspace_less_second", "second@example.com"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_same_chatgpt_id_across_workspace_ids(db_setup):
    del db_setup
    first = _account(
        "mavos_primary",
        chatgpt_account_id="chatgpt_mavos_shared",
        email="operator@example.com",
        workspace_id="ws_mavos_primary",
    )
    second = _account(
        "mavos_secondary",
        chatgpt_account_id="chatgpt_mavos_shared",
        email="operator@example.com",
        workspace_id="ws_mavos_secondary",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_primary"
    assert saved_second.id == "mavos_secondary"
    assert [(account.id, account.workspace_id) for account in accounts] == [
        ("mavos_primary", "ws_mavos_primary"),
        ("mavos_secondary", "ws_mavos_secondary"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_adds_third_workspace_slot_for_same_email(db_setup):
    del db_setup
    first = _account(
        "mavos_primary",
        chatgpt_account_id="chatgpt_mavos_primary",
        email="operator@example.com",
        workspace_id="ws_mavos_primary",
    )
    second = _account(
        "mavos_secondary",
        chatgpt_account_id="chatgpt_mavos_secondary",
        email="operator@example.com",
        workspace_id="ws_mavos_secondary",
    )
    third = _account(
        "mavos_tertiary",
        chatgpt_account_id="chatgpt_mavos_tertiary",
        email="operator@example.com",
        workspace_id="ws_mavos_tertiary",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        saved_third = await repo.upsert_account_slot(third, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_primary"
    assert saved_second.id == "mavos_secondary"
    assert saved_third.id == "mavos_tertiary"
    assert [(account.id, account.workspace_id) for account in accounts] == [
        ("mavos_primary", "ws_mavos_primary"),
        ("mavos_secondary", "ws_mavos_secondary"),
        ("mavos_tertiary", "ws_mavos_tertiary"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_preserves_same_chatgpt_id_across_workspace_labels(db_setup):
    del db_setup
    first = _account(
        "mavos_workspace",
        chatgpt_account_id="chatgpt_mavos_shared_label",
        email="operator@example.com",
        workspace_label="Mavos",
    )
    second = _account(
        "triton_workspace",
        chatgpt_account_id="chatgpt_mavos_shared_label",
        email="operator@example.com",
        workspace_label="Triton",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_workspace"
    assert saved_second.id == "triton_workspace"
    assert [(account.id, account.workspace_label) for account in accounts] == [
        ("mavos_workspace", "Mavos"),
        ("triton_workspace", "Triton"),
    ]


@pytest.mark.asyncio
async def test_upsert_account_slot_adds_third_label_only_workspace_for_same_email(db_setup):
    del db_setup
    first = _account(
        "mavos_workspace",
        chatgpt_account_id="chatgpt_label_slots",
        email="operator@example.com",
        workspace_label="Mavos",
    )
    second = _account(
        "triton_workspace",
        chatgpt_account_id="chatgpt_label_slots",
        email="operator@example.com",
        workspace_label="Triton",
    )
    third = _account(
        "atlas_workspace",
        chatgpt_account_id="chatgpt_label_slots",
        email="operator@example.com",
        workspace_label="Atlas",
    )

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        saved_first = await repo.upsert_account_slot(first, preserve_unknown_workspace_duplicates=False)
        saved_second = await repo.upsert_account_slot(second, preserve_unknown_workspace_duplicates=False)
        saved_third = await repo.upsert_account_slot(third, preserve_unknown_workspace_duplicates=False)
        accounts = await repo.list_accounts()

    assert saved_first.id == "mavos_workspace"
    assert saved_second.id == "triton_workspace"
    assert saved_third.id == "atlas_workspace"
    assert [(account.id, account.workspace_label) for account in accounts] == [
        ("mavos_workspace", "Mavos"),
        ("triton_workspace", "Triton"),
        ("atlas_workspace", "Atlas"),
    ]


@pytest.mark.asyncio
async def test_consolidate_generated_copy_duplicates_keeps_active_copy_and_usage(db_setup):
    del db_setup
    email = "copy-cleanup@example.com"
    chatgpt_account_id = "chatgpt_copy_cleanup"

    async with SessionLocal() as session:
        repo = AccountsRepository(session)
        await repo.upsert(
            _account(
                "copy-cleanup",
                chatgpt_account_id=chatgpt_account_id,
                email=email,
            ),
            merge_by_email=False,
        )
        await repo.upsert(
            _account(
                "copy-cleanup__copy2",
                chatgpt_account_id=chatgpt_account_id,
                email=email,
            ),
            merge_by_email=False,
        )
        base = await repo.get_by_id("copy-cleanup")
        copy = await repo.get_by_id("copy-cleanup__copy2")
        assert base is not None
        assert copy is not None
        base.status = AccountStatus.REAUTH_REQUIRED
        copy.status = AccountStatus.ACTIVE
        session.add(UsageHistory(account_id="copy-cleanup", window="primary", used_percent=73.0))
        await session.commit()

        removed = await repo.consolidate_generated_copy_duplicates()
        all_rows = await repo.list_accounts(refresh_existing=True, include_generated_copies=True)
        visible_rows = await repo.list_accounts(refresh_existing=True)
        latest_usage = await UsageRepository(session).latest_by_account(window="primary")

    assert removed == 1
    assert [account.id for account in all_rows if account.email == email] == ["copy-cleanup__copy2"]
    assert [account.id for account in visible_rows if account.email == email] == ["copy-cleanup__copy2"]
    assert latest_usage["copy-cleanup__copy2"].used_percent == 73.0
