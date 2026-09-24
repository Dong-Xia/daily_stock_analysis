# -*- coding: utf-8 -*-
"""B1 身份痕迹块配置默认值与注册测试。"""

import dataclasses
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestIdentityConfigDefaults(unittest.TestCase):
    def test_switch_defaults_off(self) -> None:
        from src.config import Config

        fields = {f.name: f for f in dataclasses.fields(Config)}
        for name in (
            "enable_holder_count_context",
            "enable_margin_balance_context",
            "enable_block_deals_context",
        ):
            self.assertIn(name, fields, f"missing config field: {name}")
            self.assertIs(fields[name].default, False, name)

    def test_budget_defaults(self) -> None:
        from src.config import Config

        fields = {f.name: f.default for f in dataclasses.fields(Config)}
        self.assertEqual(fields.get("identity_stage_timeout_seconds"), 30.0)
        self.assertEqual(fields.get("identity_fetch_timeout_seconds"), 10.0)
        self.assertEqual(fields.get("identity_cache_ttl_seconds"), 21600)

    def test_registry_entries_exist(self) -> None:
        from src.core.config_registry import _FIELD_DEFINITIONS

        for key in (
            "ENABLE_HOLDER_COUNT_CONTEXT",
            "ENABLE_MARGIN_BALANCE_CONTEXT",
            "ENABLE_BLOCK_DEALS_CONTEXT",
            "IDENTITY_STAGE_TIMEOUT_SECONDS",
            "IDENTITY_FETCH_TIMEOUT_SECONDS",
            "IDENTITY_CACHE_TTL_SECONDS",
        ):
            self.assertIn(key, _FIELD_DEFINITIONS, f"missing registry entry: {key}")


class TestRegistrySchemaEndpointCompat(unittest.TestCase):
    def test_registry_entries_pass_schema_response_validation(self) -> None:
        """registry 条目必须能通过 /api/v1/system/config/schema 的 pydantic 响应模型校验。"""
        from api.v1.schemas.system_config import SystemConfigSchemaResponse
        from src.core.config_registry import build_schema_response

        SystemConfigSchemaResponse.model_validate(build_schema_response())


if __name__ == "__main__":
    unittest.main()
