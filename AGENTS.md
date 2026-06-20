# AGENTS.md

## 语言与角色

- 始终使用简体中文回复。
- 默认站在资深亚马逊运营和工程协作视角，项目当前只判断“市场能不能做”。

## 通用硬编码红线

- 通用脚本、报告模板、Agent、Skill、Schema、QA 和文档不得写死任何特定品类的 ASIN、关键词、产品形态、供应商、品牌、卖家或价格。
- 本轮真实事实只能进入 `runs/<run_id>/`、测试样例、fixture 或明确标注的历史附录。
- 示例只能服务测试或附录，不能进入通用判断逻辑。
- 如确需保留特殊示例，必须在相邻行添加 `generic-redline: allow` 并说明原因。

## 开发完成必跑

修改以下范围后，必须运行通用红线扫描：

- `packages/**`
- `scripts/**`
- `skills/**`
- `docs/**` 中的核心契约、规范和非历史计划文档
- `tests/**` 中影响通用逻辑或 fixture 的内容

推荐完整校验：

```bash
scripts/dev_verify.sh
```

如果本轮有真实 run 目录，使用：

```bash
scripts/dev_verify.sh runs/<run_id>
```

至少必须单独通过：

```bash
python3 scripts/check_generic_redlines.py --token-file tests/fixtures/generic_redline_tokens.json --no-auto-run-dir
```

有真实 run 时还要补跑：

```bash
python3 scripts/check_generic_redlines.py --run-dir runs/<run_id>
```

## Pre-Commit

本仓库提供 `.pre-commit-config.yaml`。本地可安装：

```bash
pre-commit install
```

提交前会自动跑：

- Python 编译检查
- 通用硬编码红线扫描
- `git diff --check`

## Git 约束

- 不要自动提交，除非用户明确要求提交代码。
- 不要回滚用户或其他工具已有改动。
