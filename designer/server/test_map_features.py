#!/usr/bin/env python3
"""
Additional tests for Map Designer and neutral unit versions.
Run with: python3 -m unittest -v test_map_features
"""
import json
import secrets
import time
import unittest
from pathlib import Path
from test_designer_server import DesignerServerTest


class MapTest(DesignerServerTest):
    """Test map CRUD and versions."""

    def test_create_map(self):
        """Map creation succeeds."""
        token = self.register_user()
        resp = self.request('POST', '/maps', {'name': 'Test Map'}, token=token)
        self.assertIn('id', resp)
        self.assertEqual(resp['name'], 'Test Map')
        self.assertEqual(resp['current'], 1)
        self.assertEqual(resp['maxVersion'], 1)
        self.assertIn('design', resp)
        self.assertIn('images', resp['design'])
        self.assertIn('bitmaps', resp['design'])
        self.assertIn('adjacency', resp['design'])

    def test_list_maps(self):
        """Map list returns own maps."""
        token = self.register_user()
        map1 = self.request('POST', '/maps', {'name': 'Map One'}, token=token)
        map2 = self.request('POST', '/maps', {'name': 'Map Two'}, token=token)

        resp = self.request('GET', '/maps', token=token)
        self.assertIn('maps', resp)
        self.assertEqual(len(resp['maps']), 2)
        ids = {m['id'] for m in resp['maps']}
        self.assertIn(map1['id'], ids)
        self.assertIn(map2['id'], ids)

    def test_map_patch_versions(self):
        """Map patches follow version rules."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Version Test'}, token=token)
        mid = m['id']

        # First edit (addition) stays in v1
        resp = self.request('POST', f'/maps/{mid}/patch', {
            'ops': [{'op': 'set', 'path': 'images.layout', 'value': 'single'}]
        }, token=token)
        self.assertEqual(resp['current'], 1)

        # Close session so next change creates new version
        self.request('POST', f'/maps/{mid}/close-session', token=token)

        # Change creates v2
        resp = self.request('POST', f'/maps/{mid}/patch', {
            'ops': [{'op': 'set', 'path': 'images.layout', 'value': 'grid'}]
        }, token=token)
        self.assertEqual(resp['current'], 2)
        self.assertEqual(resp['maxVersion'], 2)

    def test_map_rollback(self):
        """Map rollback loads old version."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Rollback Test'}, token=token)
        mid = m['id']

        # v1: set layout to single
        self.request('POST', f'/maps/{mid}/patch', {
            'ops': [{'op': 'set', 'path': 'images.layout', 'value': 'single'}]
        }, token=token)

        # Close session so next change creates new version
        self.request('POST', f'/maps/{mid}/close-session', token=token)

        # v2: change to grid
        self.request('POST', f'/maps/{mid}/patch', {
            'ops': [{'op': 'set', 'path': 'images.layout', 'value': 'grid'}]
        }, token=token)

        # Rollback to v1
        resp = self.request('POST', f'/maps/{mid}/rollback', {'version': 1}, token=token)
        self.assertEqual(resp['current'], 1)
        self.assertEqual(resp['design']['images']['layout'], 'single')

        # Next edit creates v3 (v1 is now locked)
        resp = self.request('POST', f'/maps/{mid}/patch', {
            'ops': [{'op': 'set', 'path': 'images.layout', 'value': 'stacked'}]
        }, token=token)
        self.assertEqual(resp['current'], 3)

    def test_map_build_request(self):
        """Map build request creates console queue entry."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Build Test'}, token=token)

        resp = self.request('POST', f'/maps/{m["id"]}/request', {
            'type': 'build',
            'text': f'Build map {m["name"]}',
            'data': {'version': 1}
        }, token=token)
        self.assertEqual(resp['type'], 'build')

        # Check console queue
        if self.console_queue.exists():
            log = self.console_queue.read_text()
            self.assertIn('MAP-BUILD', log)
            self.assertIn(m['name'], log)

    def test_map_extract_request(self):
        """Map extract request creates console queue entry."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Extract Test'}, token=token)

        resp = self.request('POST', f'/maps/{m["id"]}/request', {
            'type': 'extract',
            'text': f'Extract regions for {m["name"]}',
            'data': {'target': 'regions'}
        }, token=token)
        self.assertEqual(resp['type'], 'extract')

        # Check console queue
        if self.console_queue.exists():
            log = self.console_queue.read_text()
            self.assertIn('MAP-EXTRACT', log)

    def test_map_bug_request(self):
        """Map bug request creates console queue entry."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Bug Test'}, token=token)

        # Set build status to built first
        admin_resp = self.request('POST', f'/admin/{self.admin_token}/maps/{m["id"]}/build-status', {
            'status': 'built',
            'version': 1
        })

        resp = self.request('POST', f'/maps/{m["id"]}/request', {
            'type': 'bug',
            'text': 'Bug report',
            'data': {'description': 'Region names are wrong'}
        }, token=token)
        self.assertEqual(resp['type'], 'bug')

        # Check console queue
        if self.console_queue.exists():
            log = self.console_queue.read_text()
            self.assertIn('MAP-BUG', log)


class UnitVersionsTest(DesignerServerTest):
    """Test neutral unit versions."""

    def test_unit_versions_migration(self):
        """Old units get versions on first load."""
        token = self.register_user()

        # Create unit (new units should have versions from the start)
        unit = self.request('POST', '/units', {'name': 'Test Monster'}, token=token)
        uid = unit['id']

        # Get unit - should have versions
        resp = self.request('GET', f'/units/{uid}', token=token)
        self.assertIn('current', resp)
        self.assertIn('maxVersion', resp)
        self.assertIn('versions', resp)
        self.assertEqual(resp['current'], 1)

    def test_unit_patch_versions(self):
        """Unit patches follow version rules."""
        token = self.register_user()
        unit = self.request('POST', '/units', {'name': 'Version Unit'}, token=token)
        uid = unit['id']
        row_id = unit['design']['units']['rows'][0]['id']

        # First edit (addition) stays in v1
        resp = self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.type', 'value': 'Monster'}]
        }, token=token)
        self.assertEqual(resp['current'], 1)

        # Close session so next change creates new version
        self.request('POST', f'/units/{uid}/close-session', token=token)

        # Change creates v2
        resp = self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.type', 'value': 'Terror'}]
        }, token=token)
        self.assertEqual(resp['current'], 2)

    def test_unit_rollback(self):
        """Unit rollback loads old version."""
        token = self.register_user()
        unit = self.request('POST', '/units', {'name': 'Rollback Unit'}, token=token)
        uid = unit['id']
        row_id = unit['design']['units']['rows'][0]['id']

        # v1: set type
        self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.type', 'value': 'Monster'}]
        }, token=token)

        # Close session so next change creates new version
        self.request('POST', f'/units/{uid}/close-session', token=token)

        # v2: change type
        self.request('POST', f'/units/{uid}/patch', {
            'ops': [{'op': 'set', 'path': f'units.rows.{row_id}.type', 'value': 'Terror'}]
        }, token=token)

        # Rollback to v1
        resp = self.request('POST', f'/units/{uid}/rollback', {'version': 1}, token=token)
        self.assertEqual(resp['current'], 1)
        self.assertEqual(resp['design']['units']['rows'][0]['type'], 'Monster')

    def test_unit_bug_request(self):
        """Unit bug request creates console queue entry."""
        token = self.register_user()
        unit = self.request('POST', '/units', {'name': 'Bug Unit'}, token=token)

        # Set build status to built first
        admin_resp = self.request('POST', f'/admin/{self.admin_token}/units/{unit["id"]}/build-status', {
            'status': 'built',
            'version': 1
        })

        resp = self.request('POST', f'/units/{unit["id"]}/request', {
            'type': 'bug',
            'text': 'Bug report',
            'data': {'description': 'Combat values are wrong'}
        }, token=token)
        self.assertEqual(resp['type'], 'bug')

        # Check console queue
        if self.console_queue.exists():
            log = self.console_queue.read_text()
            self.assertIn('UNIT-BUG', log)


class AdminMapTest(DesignerServerTest):
    """Test admin map endpoints."""

    def test_admin_get_map(self):
        """Admin can get any map."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Admin Map'}, token=token)

        # Admin GET
        resp = self.request('GET', f'/admin/{self.admin_token}/maps/{m["id"]}')
        self.assertEqual(resp['id'], m['id'])
        self.assertEqual(resp['name'], 'Admin Map')

    def test_admin_map_patch(self):
        """Admin can patch any map."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Patch Map'}, token=token)

        resp = self.request('POST', f'/admin/{self.admin_token}/maps/{m["id"]}/patch', {
            'ops': [{'op': 'set', 'path': 'images.layout', 'value': 'grid'}]
        })
        self.assertEqual(resp['current'], 1)

    def test_admin_map_build_status(self):
        """Admin can set map build status."""
        token = self.register_user()
        m = self.request('POST', '/maps', {'name': 'Status Map'}, token=token)

        resp = self.request('POST', f'/admin/{self.admin_token}/maps/{m["id"]}/build-status', {
            'status': 'built',
            'version': 1
        })
        self.assertEqual(resp['ok'], True)

        # Verify status changed
        updated_map = self.request('GET', f'/maps/{m["id"]}', token=token)
        self.assertEqual(updated_map['build']['status'], 'built')
        self.assertEqual(updated_map['build']['liveVersion'], 1)


if __name__ == '__main__':
    unittest.main()
