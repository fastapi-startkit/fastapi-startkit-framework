import os
import unittest
from unittest import mock

from fastapi_startkit.ai import AIConfig, BedrockConfig
from fastapi_startkit.ai.lab import Lab
from fastapi_startkit.application import app

AWS_ENV = (
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
    "AWS_BEARER_TOKEN_BEDROCK",
    "AWS_BEDROCK_MODEL",
)


class BedrockTestCase(unittest.TestCase):
    def use_env(self, values=None):
        patcher = mock.patch.dict(os.environ, values or {})
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in AWS_ENV:
            if key not in (values or {}):
                os.environ.pop(key, None)

    def use_config(self, bedrock: BedrockConfig | None = None):
        config = AIConfig()
        if bedrock is not None:
            config.providers["bedrock"] = bedrock
        app().make("config").set("ai", config)


class TestBedrockConfig(BedrockTestCase):
    def test_defaults_are_empty_without_aws_env(self):
        self.use_env()
        config = BedrockConfig()

        self.assertEqual(config.driver, "bedrock")
        self.assertEqual(
            (
                config.key,
                config.region,
                config.access_key_id,
                config.secret_access_key,
                config.session_token,
                config.profile,
            ),
            ("", "", "", "", "", ""),
        )
        self.assertEqual(config.models["default"], "us.anthropic.claude-sonnet-4-6")

    def test_reads_aws_env(self):
        self.use_env(
            {
                "AWS_REGION": "eu-west-1",
                "AWS_ACCESS_KEY_ID": "AKIATEST",
                "AWS_SECRET_ACCESS_KEY": "secret",
                "AWS_SESSION_TOKEN": "token",
                "AWS_PROFILE": "dev",
                "AWS_BEARER_TOKEN_BEDROCK": "bedrock-key",
                "AWS_BEDROCK_MODEL": "amazon.nova-pro-v1:0",
            }
        )
        config = BedrockConfig()

        self.assertEqual(config.region, "eu-west-1")
        self.assertEqual(config.access_key_id, "AKIATEST")
        self.assertEqual(config.secret_access_key, "secret")
        self.assertEqual(config.session_token, "token")
        self.assertEqual(config.profile, "dev")
        self.assertEqual(config.key, "bedrock-key")
        self.assertEqual(config.models["default"], "amazon.nova-pro-v1:0")

    def test_region_falls_back_to_default_region(self):
        self.use_env({"AWS_DEFAULT_REGION": "ap-south-1"})
        self.assertEqual(BedrockConfig().region, "ap-south-1")

    def test_region_prefers_aws_region(self):
        self.use_env({"AWS_REGION": "us-west-2", "AWS_DEFAULT_REGION": "ap-south-1"})
        self.assertEqual(BedrockConfig().region, "us-west-2")

    def test_registered_in_ai_config(self):
        self.assertIsInstance(AIConfig().providers["bedrock"], BedrockConfig)


class TestBedrockLab(BedrockTestCase):
    def test_resolves_bedrock_provider(self):
        self.use_env()
        self.use_config()

        self.assertIs(Lab.get_provider("bedrock"), Lab.BEDROCK)
        self.assertEqual(Lab.BEDROCK.get_provider_key(), "bedrock_converse")
        self.assertEqual(Lab.get_model_url("bedrock"), "bedrock_converse:us.anthropic.claude-sonnet-4-6")

    def test_client_options_map_credentials(self):
        self.use_config(
            BedrockConfig(
                region="us-east-1",
                access_key_id="AKIATEST",
                secret_access_key="secret",
                session_token="token",
                profile="dev",
            )
        )

        self.assertEqual(
            Lab.BEDROCK.get_client_options(),
            {
                "region_name": "us-east-1",
                "aws_access_key_id": "AKIATEST",
                "aws_secret_access_key": "secret",
                "aws_session_token": "token",
                "credentials_profile_name": "dev",
            },
        )

    def test_client_options_omit_unset_values_for_default_credential_chain(self):
        self.use_env()
        self.use_config()

        self.assertEqual(Lab.BEDROCK.get_client_options(), {})
        self.assertFalse(Lab.BEDROCK.get_api_key())

    def test_other_providers_have_no_client_options(self):
        self.use_config()

        for lab in (Lab.GOOGLE, Lab.OPENAI, Lab.ANTHROPIC, Lab.ELEVENLABS):
            self.assertEqual(lab.get_client_options(), {})
