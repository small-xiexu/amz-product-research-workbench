from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "skills" / "amazon-product-research" / "agent_manifest.json"


class AgentAdapterSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.agents = cls.manifest["agents"]

    def test_manifest_covers_all_runtime_agents(self) -> None:
        self.assertEqual(self.manifest["schema_version"], "agent-manifest-v1")
        self.assertEqual(self.manifest["manifest_scope"], "runtime_routing_only")
        self.assertIn("runtime discovery hint", self.manifest["description_policy"])
        self.assertIn("routing_hint", self.manifest["description_policy"])
        self.assertIn(
            "skills/amazon-product-research/references/runtime_rules.md",
            self.manifest["canonical_references"],
        )
        self.assertEqual(len(self.agents), 16)
        ids = [agent["id"] for agent in self.agents]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("sellersprite-quick-agent", ids)
        self.assertIn("growth-risk-agent", ids)
        self.assertIn("delivery-qa-agent", ids)

    def test_manifest_source_files_exist_and_have_runtime_metadata(self) -> None:
        required_fields = {
            "id",
            "display_name",
            "source_file",
            "stage",
            "category",
            "routing_hint",
            "outputs",
            "validation_commands",
            "fallback_policy",
            "max_retries",
            "tools_profile",
        }
        for agent in self.agents:
            with self.subTest(agent=agent["id"]):
                self.assertFalse(required_fields - set(agent))
                self.assertNotIn("description", agent)
                self.assertTrue((ROOT / agent["source_file"]).is_file())
                self.assertTrue(agent["outputs"])
                self.assertIsInstance(agent["validation_commands"], list)

    def test_generated_adapters_are_in_sync(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/generate_agent_adapters.py", "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("agent adapters: OK", result.stdout)

    def test_claude_and_codex_adapters_exist_for_every_agent(self) -> None:
        for agent in self.agents:
            with self.subTest(agent=agent["id"]):
                source_hash = _sha256(ROOT / agent["source_file"])
                claude_path = ROOT / ".claude" / "agents" / f"{agent['id']}.md"
                codex_path = ROOT / ".codex" / "agents" / f"{agent['id']}.toml"
                self.assertTrue(claude_path.is_file())
                self.assertTrue(codex_path.is_file())

                claude_text = claude_path.read_text(encoding="utf-8")
                codex_text = codex_path.read_text(encoding="utf-8")
                source_heading = (ROOT / agent["source_file"]).read_text(
                    encoding="utf-8"
                ).splitlines()[0]
                self.assertIn(f"name: {agent['id']}", claude_text)
                self.assertIn(f"name = \"{agent['id'].replace('-', '_')}\"", codex_text)
                self.assertIn(f"source_sha256: `{source_hash}`", claude_text)
                self.assertIn(f"# source_sha256 = {source_hash}", codex_text)
                self.assertIn("routing_hint is only for runtime discovery", claude_text)
                self.assertIn("routing_hint is only for runtime discovery", codex_text)
                self.assertIn("## Canonical Agent Instructions", claude_text)
                self.assertIn("## Canonical Agent Instructions", codex_text)
                self.assertIn(source_heading, claude_text)
                self.assertIn(source_heading, codex_text)
                self.assertIn("developer_instructions", codex_text)

    def test_codex_skill_adapter_points_to_canonical_skill(self) -> None:
        skill_path = ROOT / ".agents" / "skills" / "amazon-product-research" / "SKILL.md"
        self.assertTrue(skill_path.is_file())
        text = skill_path.read_text(encoding="utf-8")
        self.assertIn("runtime_rules.md", text)
        self.assertIn("canonical_skill: `skills/amazon-product-research/SKILL.md`", text)
        self.assertIn("Do not copy or reinterpret the workflow", text)

    def test_root_runtime_rules_exist_and_share_core_boundaries(self) -> None:
        ag = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        cl = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        runtime_rules = (
            ROOT / "skills" / "amazon-product-research" / "references" / "runtime_rules.md"
        ).read_text(encoding="utf-8")
        for text in (ag, cl):
            self.assertIn("skills/amazon-product-research/references/runtime_rules.md", text)
            self.assertIn("不要自动提交", text)
            self.assertNotIn("## 多 Agent 边界", text)
            self.assertNotIn("## 脚本边界", text)
        self.assertIn("Lead Operator Agent 是唯一有权输出最终放行判断", runtime_rules)
        self.assertIn("脚本负责契约校验、确定性生成、seed、XLSX、QA、断点审计", runtime_rules)
        self.assertIn("manifest.json` | 只存运行时路由元数据", runtime_rules)

    def test_runtime_adapter_dirs_are_not_gitignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        ignored_patterns = {
            line.strip()
            for line in gitignore.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
        self.assertNotIn(".claude/", ignored_patterns)
        self.assertNotIn(".claude/agents/", ignored_patterns)
        self.assertNotIn(".codex/", ignored_patterns)
        self.assertNotIn(".codex/agents/", ignored_patterns)
        self.assertNotIn(".agents/", ignored_patterns)
        self.assertNotIn(".agents/skills/", ignored_patterns)
        self.assertIn(".claude/settings.local.json", ignored_patterns)
        self.assertIn(".claude/reviews/", ignored_patterns)
        self.assertIn(".claude/worktrees/", ignored_patterns)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
