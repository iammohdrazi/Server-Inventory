#!/usr/bin/env python3
"""
ServerInventory — Unit Tests
Tests for core modules: config, descriptions, auth token generation.
"""

import os
import sys
import json
import unittest

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))


class TestConfig(unittest.TestCase):
    """Test configuration module."""

    def test_config_version(self):
        from config import Config
        self.assertIsInstance(Config.VERSION, str)
        self.assertRegex(Config.VERSION, r'^\d+\.\d+\.\d+$')

    def test_config_port(self):
        from config import Config
        self.assertIsInstance(Config.PORT, int)
        self.assertGreater(Config.PORT, 0)
        self.assertLess(Config.PORT, 65536)

    def test_config_secret_key(self):
        from config import Config
        self.assertIsInstance(Config.SECRET_KEY, str)
        self.assertGreater(len(Config.SECRET_KEY), 16)

    def test_config_session_timeout(self):
        from config import Config
        self.assertIsInstance(Config.SESSION_TIMEOUT, int)
        self.assertGreater(Config.SESSION_TIMEOUT, 0)


class TestDescriptions(unittest.TestCase):
    """Test service descriptions module."""

    def test_descriptions_exist(self):
        from descriptions import DESCRIPTIONS
        self.assertGreater(len(DESCRIPTIONS), 30)

    def test_get_description(self):
        from descriptions import get_description
        desc = get_description('sshd')
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_get_full_description(self):
        from descriptions import get_full_description
        info = get_full_description('nginx')
        self.assertIsNotNone(info)
        self.assertIn('name', info)
        self.assertIn('description', info)
        self.assertIn('category', info)

    def test_unknown_service(self):
        from descriptions import get_description
        desc = get_description('totally_unknown_service_12345')
        self.assertEqual(desc, '')

    def test_all_descriptions_have_required_fields(self):
        from descriptions import DESCRIPTIONS
        for name, info in DESCRIPTIONS.items():
            self.assertIn('name', info, f"Missing 'name' in {name}")
            self.assertIn('short', info, f"Missing 'short' in {name}")
            self.assertIn('description', info, f"Missing 'description' in {name}")
            self.assertIn('category', info, f"Missing 'category' in {name}")


class TestAuth(unittest.TestCase):
    """Test authentication token functions."""

    def test_create_and_verify_token(self):
        from auth import create_token, verify_token
        token = create_token('testuser')
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)

        payload = verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['sub'], 'testuser')
        self.assertEqual(payload['type'], 'access')

    def test_create_refresh_token(self):
        from auth import create_refresh_token, verify_token
        token = create_refresh_token('testuser')
        payload = verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['type'], 'refresh')

    def test_invalid_token(self):
        from auth import verify_token
        result = verify_token('invalid.token.here')
        self.assertIsNone(result)

    def test_empty_token(self):
        from auth import verify_token
        result = verify_token('')
        self.assertIsNone(result)

    def test_jwt_required_socket(self):
        from auth import jwt_required_socket, create_token
        # Valid token
        token = create_token('socketuser')
        user = jwt_required_socket(token)
        self.assertEqual(user, 'socketuser')

        # Invalid token
        user = jwt_required_socket('bad_token')
        self.assertIsNone(user)

        # None
        user = jwt_required_socket(None)
        self.assertIsNone(user)


class TestModuleImports(unittest.TestCase):
    """Test that all server modules can be imported."""

    def test_import_config(self):
        import config
        self.assertIsNotNone(config.Config)

    def test_import_descriptions(self):
        import descriptions
        self.assertIsNotNone(descriptions.DESCRIPTIONS)

    def test_import_auth(self):
        import auth
        self.assertIsNotNone(auth.auth_bp)

    def test_import_hardware(self):
        import api_hardware
        self.assertIsNotNone(api_hardware.hardware_bp)

    def test_import_software(self):
        import api_software
        self.assertIsNotNone(api_software.software_bp)

    def test_import_network(self):
        import api_network
        self.assertIsNotNone(api_network.network_bp)

    def test_import_storage(self):
        import api_storage
        self.assertIsNotNone(api_storage.storage_bp)

    def test_import_services(self):
        import api_services
        self.assertIsNotNone(api_services.services_bp)

    def test_import_files(self):
        import api_files
        self.assertIsNotNone(api_files.files_bp)

    def test_import_settings(self):
        import api_settings
        self.assertIsNotNone(api_settings.settings_bp)

    def test_import_system(self):
        import api_system
        self.assertIsNotNone(api_system.system_bp)


if __name__ == '__main__':
    unittest.main()
