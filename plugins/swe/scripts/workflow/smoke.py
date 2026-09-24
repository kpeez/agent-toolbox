#!/usr/bin/env python3
"""Small offline smoke set. Run directly; only temporary synthetic data is used."""
import copy
import datetime
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import adapters
import audit
import core
import demo


class LinearTransport:
    """Controlled GraphQL transport exercises the real adapter without a server."""
    def __init__(self):
        self.data = {}
        self.calls = []
        self.outage = False
        self.lose_kind = None

    def __call__(self, query, variables):
        self.calls.append((query, copy.deepcopy(variables)))
        if self.outage:
            raise adapters.AdapterError('network_error', 'synthetic outage')
        if '__type' in query:
            data = {'mutationType': {'fields': [{'name': m} for _, m, _ in adapters._CREATE_META]}}
            for alias in adapters._CAPABILITY_TYPE_ALIASES:
                data[alias] = {'fields': [{'name': 'id'}, {'name': 'status'}]}
            for alias in adapters._CAPABILITY_INPUT_ALIASES:
                data[alias] = {'inputFields': [{'name': 'id', 'type': {'kind': 'SCALAR'}}]}
            return {'data': data}
        for kind, document in adapters._GET_QUERIES.items():
            if query == document:
                return {'data': {adapters._GET_RESULT_KEYS[kind]: copy.deepcopy(self.data.get((kind, variables['id'])))}}
        for kind, document in adapters._CREATE_QUERIES.items():
            if query != document:
                continue
            payload = variables['input']
            identity = payload['id']
            node = dict(payload, archivedAt=None, updatedAt='2026-01-01T00:00:00Z')
            for field in ('project', 'issue', 'team', 'relatedIssue'):
                if payload.get(field + 'Id'):
                    node[field] = {'id': payload[field + 'Id']}
            if kind == 'project':
                node['teams'] = {'nodes': [{'id': x} for x in payload['teamIds']]}
            if kind == 'issue':
                node['labels'] = {'nodes': [{'id': x} for x in payload.get('labelIds', [])], 'pageInfo': {'hasNextPage': False}}
                node['state'] = {'id': payload['stateId'], 'name': 'Todo', 'type': 'unstarted'}
            self.data.setdefault((kind, identity), node)
            if self.lose_kind == kind:
                self.lose_kind = None
                self.outage = True
                raise adapters.AdapterError('network_error', 'synthetic lost response')
            return {'data': {adapters._CREATE_MUTATION_KEYS[kind]: {'success': True, adapters._CREATE_OBJECT_KEYS[kind]: copy.deepcopy(node)}}}
        raise AssertionError('Unexpected GraphQL operation')


class WorkflowSmoke(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.packet, self.config, self.authority = demo.fixture(self.root)
        self.store = core.Store(str(self.root / 'state.json'))
        self.addCleanup(self.store.close)
        self.adapter = adapters.FakeAdapter()

    def publish(self, **kwargs):
        return core.publish(self.packet, self.config, self.authority, apply=True,
                            store=self.store, adapter=kwargs.get('adapter', self.adapter))

    def note(self, **overrides):
        value = {'request_id': core.new_uuid4(), 'task_id': self.packet['tasks'][0]['task_id'],
                 'kind': 'handoff', 'observed_at': core.now_iso(), 'summary': 'Synthetic work is ready for review.',
                 'facts': {'owner': 'synthetic-agent', 'running_jobs': [], 'condition': 'awaiting_input'},
                 'next_action': 'Inspect the issue evidence and current checkout.'}
        value.update(overrides)
        return value

    def record(self, request):
        return core.record(self.packet, self.config, request, apply=True, store=self.store,
                           adapter=self.adapter, authority=self.authority)

    def test_approval_digest_and_context(self):
        original = core.semantic_digest(self.packet)
        self.packet['spec']['metadata'].update(approved=True, tracker_container='synthetic-project')
        self.assertEqual(original, core.semantic_digest(self.packet))
        self.packet['spec']['markdown'] += '\nChanged acceptance intent.'
        with self.assertRaises(core.CoreError):
            self.publish()
        self.packet['context'][0]['path'] = 'missing.md'
        self.assertTrue(core.collect_validation_errors(self.packet, self.config))

    def test_preview_and_permission_denial_do_not_publish(self):
        state_path = self.root / 'preview-only.json'
        store = core.Store(str(state_path), readonly=True)
        result = core.publish(self.packet, self.config, {}, store=store, adapter=self.adapter)
        self.assertFalse(result['applied'])
        self.assertFalse(result['ok'])
        self.assertFalse(result['can_apply'])
        self.assertFalse(state_path.exists())
        self.assertEqual(self.adapter.data, {})
        self.authority['permission']['actions'] = []
        with self.assertRaises(core.CoreError):
            self.publish()
        self.assertEqual(self.adapter.data, {})
        self.authority['permission'].update(actions=['publish'], project_id=core.new_uuid4(), create_project=True)
        with self.assertRaises(core.CoreError):
            self.publish()
        self.assertEqual(self.adapter.data, {})

    def test_real_linear_repeat_and_ambiguous_write_recovery(self):
        transport = LinearTransport()
        adapter = adapters.LinearAdapter('synthetic', transport=transport)
        transport.lose_kind = 'issue'
        with self.assertRaises(core.CoreError):
            self.publish(adapter=adapter)
        issue_ids = [identity for kind, identity in transport.data if kind == 'issue']
        transport.outage = False
        self.publish(adapter=adapter)
        before = copy.deepcopy(transport.data)
        self.publish(adapter=adapter)
        self.assertEqual(before, transport.data)
        self.assertEqual(issue_ids, [identity for kind, identity in transport.data if kind == 'issue'])
        self.assertEqual(sum(q == adapters._CREATE_QUERIES['issue'] for q, _ in transport.calls), 1)

    def test_human_edit_and_missing_archived_project_preserved(self):
        self.publish()
        document = next(iter(self.adapter.data['document'].values()))
        old = document['content']
        document['content'] = 'Human revision'
        with self.assertRaises(core.CoreError):
            self.publish()
        self.assertEqual(document['content'], 'Human revision')
        document['content'] = old
        self.packet['spec']['markdown'] += '\nApproved clarification.'
        self.authority['spec_approval']['digest'] = core.semantic_digest(self.packet)
        revised = self.publish()
        item = next(item for item in revised['actions'] if item.get('revision_comment'))
        self.assertEqual(item['action'], 'append_revision')
        self.assertEqual(item['revision_comment']['kind'], 'comment')
        project_id, project = next(iter(self.adapter.data['project'].items()))
        project['archived'] = True
        with self.assertRaises(core.CoreError):
            self.publish()
        self.adapter.data['project'].pop(project_id)
        with self.assertRaises(core.CoreError):
            self.publish()
        self.assertEqual(self.adapter.data['project'], {})

    def test_handoff_retry_stale_observation_and_hold(self):
        result = self.publish()
        self.authority['permission']['project_id'] = result['mappings']['tracker_container']
        issue = next(iter(self.adapter.data['issue'].values()))
        issue['label_ids'] = [self.config['integration']['needs_human_label_id']]
        before = copy.deepcopy(issue)
        note = self.note()
        self.record(note)
        self.record(note)
        self.assertEqual(len(self.adapter.data['comment']), 1)
        self.assertEqual(before, issue)
        with self.assertRaises(core.CoreError):
            self.record(dict(note, summary='Reused id with altered content'))
        with self.assertRaises(core.CoreError):
            self.record(self.note(observed_at='2020-01-01T00:00:00Z'))
        self.authority['permission']['project_id'] = core.new_uuid4()
        with self.assertRaises(core.CoreError):
            self.record(self.note())
        self.assertEqual(len(self.adapter.data['comment']), 1)

    def test_real_adapter_denial_and_malformed_read(self):
        cases = (({'errors': [{'extensions': {'type': 'forbidden'}}]}, 'permission_denied'),
                 ({'data': {}}, 'malformed_response'))
        for envelope, code in cases:
            adapter = adapters.LinearAdapter('synthetic', transport=lambda q, v: envelope)
            with self.assertRaises(adapters.AdapterError) as caught:
                adapter.get('issue', core.new_uuid4())
            self.assertEqual(caught.exception.code, code)

    def test_public_text_gate(self):
        for text in ('https://linear.app/example/issue/ABC-123', 'ABC-123', '/Users/example/private.md', 'token=private-value'):
            with self.assertRaises(core.CoreError):
                core.assert_public_text_safe(text, self.config)
        core.assert_public_text_safe('Preserve ordering. Unit checks passed.', self.config)
        with self.assertRaises(core.CoreError):
            core.publish(self.packet, self.config, {}, destination='public')

    def test_real_github_evidence_and_readonly_audit(self):
        self.publish()
        task = self.packet['tasks'][0]
        pr = task['completion']['required_prs'][0]
        raw = {'head': {'sha': pr['head_sha']}, 'base': {'ref': task['base_branch']},
               'draft': False, 'merged': True, 'merge_commit_sha': 'b' * 40}
        checks = [{'name': name, 'head_sha': pr['head_sha'], 'conclusion': 'success'} for name in pr['required_checks']]
        reviews = [{'user': {'login': actor}, 'commit_id': pr['head_sha'], 'state': 'APPROVED'} for actor in pr['required_reviewers']]
        def transport(method, path):
            self.assertEqual(method, 'GET')
            if '/check-runs?' in path: return {'total_count': len(checks), 'check_runs': copy.deepcopy(checks)}
            if '/status?' in path: return {'total_count': 0, 'statuses': []}
            if '/reviews?' in path: return copy.deepcopy(reviews)
            return copy.deepcopy(raw)
        evidence = adapters.GitHubEvidence(transport=transport)
        self.assertEqual(core.verify_code_completion(task, self.config, evidence), [])
        before = copy.deepcopy(self.adapter.data)
        result = audit.audit(self.packet, self.config, evidence, store=self.store, adapter=self.adapter)
        self.assertFalse(result['applied'])
        self.assertTrue(result['ok'])
        self.assertEqual(result['findings'], [])
        self.assertTrue(result['tasks'][0]['code_delivery_evidence_satisfied'])
        self.assertEqual(before, self.adapter.data)
        for mutation in ('branch', 'draft', 'checks', 'reviews', 'head', 'extra_pr'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(task)
                raw['base']['ref'] = 'wrong' if mutation == 'branch' else task['base_branch']
                raw['draft'] = mutation == 'draft'
                raw['head']['sha'] = 'c' * 40 if mutation == 'head' else pr['head_sha']
                checks[0]['conclusion'] = 'failure' if mutation == 'checks' else 'success'
                reviews[0]['state'] = 'CHANGES_REQUESTED' if mutation == 'reviews' else 'APPROVED'
                if mutation == 'extra_pr': changed['completion']['required_prs'].append(dict(pr, number=None))
                self.assertTrue(core.verify_code_completion(changed, self.config, evidence))


if __name__ == '__main__':
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden in smoke checks')):
        unittest.main(verbosity=2)
