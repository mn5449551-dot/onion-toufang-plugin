import re
import unittest
import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HARDCODED_PLUGIN_ROOT_FRAGMENT = "app_tixiao/skill_toufang/onion-toufang-plugin"


class SkillContractTests(unittest.TestCase):
    def iter_docs(self):
        for root in (PLUGIN_ROOT / "skills", PLUGIN_ROOT / "shared"):
            yield from root.rglob("*.md")
        yield PLUGIN_ROOT / "README.md"

    def iter_text_files(self):
        text_suffixes = {".md", ".json", ".py", ".toml", ".template", ".txt", ".html"}
        skip_dirs = {".git", "__pycache__", ".pytest_cache"}
        for path in PLUGIN_ROOT.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix in text_suffixes or path.name.startswith(".env"):
                yield path

    def test_runtime_docs_do_not_hardcode_local_plugin_root(self):
        offenders = []
        for path in self.iter_docs():
            text = path.read_text(encoding="utf-8")
            if HARDCODED_PLUGIN_ROOT_FRAGMENT in text:
                offenders.append(str(path.relative_to(PLUGIN_ROOT)))

        self.assertEqual(offenders, [])

    def test_repository_does_not_expose_real_people_or_personal_paths(self):
        banned = [
            "徐" + "豪",
            "王" + "雪" + "纯",
            "/Users/" + "xhh",
        ]
        offenders = []
        for path in self.iter_text_files():
            text = path.read_text(encoding="utf-8")
            for item in banned:
                if item in text:
                    offenders.append(f"{path.relative_to(PLUGIN_ROOT)} -> {item}")

        self.assertEqual(offenders, [])

    def test_base_schema_pending_and_field_count_are_consistent(self):
        text = (PLUGIN_ROOT / "shared" / "base_schema.md").read_text(encoding="utf-8")

        self.assertIn("## 表 2：`copies`（文案，14 字段）", text)
        self.assertIn("飞书 auto_number 是字段级递增计数", text)
        self.assertNotIn("下次启动 skill 自动补", text)

    def test_direction_selling_points_base_field_is_text_not_select(self):
        schema = (PLUGIN_ROOT / "shared" / "base_schema.md").read_text(encoding="utf-8")
        direction_rules = (PLUGIN_ROOT / "skills" / "onion-direction" / "references" / "字段与生成规则.md").read_text(encoding="utf-8")
        knowledge = (PLUGIN_ROOT / "shared" / "knowledge" / "卖点库.md").read_text(encoding="utf-8")
        skill = (PLUGIN_ROOT / "skills" / "onion-direction" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("| `卖点` | text | ✅ |", schema)
        self.assertIn("写入 Base 时传文本", schema)
        self.assertIn('"识别准确；AI+名师校准"', schema)
        self.assertNotIn("| `卖点` | select 多 |", schema)
        self.assertNotIn('["识别准确", "AI+名师校准"]', schema)

        self.assertIn("| 卖点 | 文本", direction_rules)
        self.assertIn("不要传数组", direction_rules)
        self.assertIn("卖点` 是文本字段", knowledge)
        self.assertIn("Base 的 `卖点` 字段是 text", skill)

    def test_image_group_dynamic_fields_are_text_for_current_plugin(self):
        schema = (PLUGIN_ROOT / "shared" / "base_schema.md").read_text(encoding="utf-8")
        visual = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "视觉元素规范.md").read_text(encoding="utf-8")

        self.assertIn("| `版位` | text |", schema)
        self.assertIn("| `比例` | text |", schema)
        self.assertIn("| `IP形象` | text |", schema)
        self.assertIn("不要做成固定选项", schema)
        self.assertIn("Base 的 `IP形象` 是文本字段", visual)
        self.assertIn("不要依赖固定选项", visual)

    def test_referenced_shared_scripts_exist(self):
        missing = []
        pattern = re.compile(r"shared/scripts/([A-Za-z0-9_]+\.py)")
        for path in self.iter_docs():
            text = path.read_text(encoding="utf-8")
            for script_name in pattern.findall(text):
                script_path = PLUGIN_ROOT / "shared" / "scripts" / script_name
                if not script_path.exists():
                    missing.append(f"{path.relative_to(PLUGIN_ROOT)} -> {script_name}")

        self.assertEqual(missing, [])

    def test_skill_docs_use_skill_relative_shared_paths(self):
        offenders = []
        pattern = re.compile(r"(?<!\.\./\.\./)(?<!\w)shared/")
        for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                offenders.append(f"{path.relative_to(PLUGIN_ROOT)}:{text[:match.start()].count(chr(10)) + 1}")

        self.assertEqual(offenders, [])

    def test_codex_plugin_manifest_exists_without_placeholders(self):
        manifest_path = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
        self.assertTrue(manifest_path.exists())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "onion-toufang")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertNotIn("<", json.dumps(manifest, ensure_ascii=False))

    def test_using_skill_defines_top_level_dispatch_rules_without_router_skill(self):
        text = (PLUGIN_ROOT / "skills" / "onion-using" / "SKILL.md").read_text(encoding="utf-8")
        evals = json.loads((PLUGIN_ROOT / "skills" / "onion-using" / "evals" / "evals.json").read_text(encoding="utf-8"))
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertFalse((PLUGIN_ROOT / "skills" / "onion-router").exists())
        self.assertIn("使用协议", text)
        self.assertIn("分诊规则", text)
        self.assertIn("不生成方向、不写文案、不生图、不写 Base", text)
        self.assertIn("D-XXX", text)
        self.assertIn("C-XXX", text)
        self.assertIn("G-XXX", text)
        self.assertIn("选择第 N 条", text)
        self.assertIn("上传图先判断角色", text)
        self.assertIn("旧广告图锚点", text)
        self.assertIn("APP 截图、风格参考图或 IP 参考图", text)
        self.assertIn("口头选择 set", text)
        self.assertIn("onion-help", text)
        self.assertNotIn("onion-router", readme)

        cases = {item["name"]: item["expected_output"] for item in evals["evals"]}
        self.assertIn("D-XXX 不能直接出图", cases["direction-id-image-request-routes-to-copy"])
        self.assertIn("仍走 onion-image", cases["uploaded-reference-image-does-not-route-to-iterate"])
        self.assertIn("onion-image-iterate", cases["uploaded-old-ad-routes-to-iterate"])
        self.assertIn("不能口头选择 set", cases["oral-image-selection-routes-to-selection-page-result"])

    def test_superpowers_style_bootstrap_and_router_scope_are_explicit(self):
        using_path = PLUGIN_ROOT / "skills" / "onion-using" / "SKILL.md"
        self.assertTrue(using_path.exists())
        using = using_path.read_text(encoding="utf-8")
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        claude_marketplace = json.loads((PLUGIN_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

        self.assertIn("不是中心业务执行器", using)
        self.assertIn("明确任务直接进入对应原子 skill", using)
        self.assertIn("歧义、跨边界、D/C/G ID、上传图用途不明、选择第 N 条", using)
        self.assertIn("每个原子 skill 必须能独立整理 Input Envelope", using)
        self.assertIn("onion-using", readme)
        self.assertIn("skills/onion-using", claude_marketplace["plugins"][0]["skills"])
        self.assertNotIn("skills/onion-router", claude_marketplace["plugins"][0]["skills"])

        for skill_name in ("onion-direction", "onion-copy", "onion-image", "onion-image-iterate"):
            text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("入口门禁", text, skill_name)
            self.assertIn("越界", text, skill_name)

    def test_all_skills_use_shared_input_envelope_contract(self):
        envelope = (PLUGIN_ROOT / "shared" / "references" / "input-envelope.md").read_text(encoding="utf-8")
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("不是让用户填写的表单", envelope)
        self.assertIn("凡是会影响工具调用、Base 写入、HTML 页面、生图 API 或下游 skill 的字段必须结构化", envelope)
        self.assertIn('"stage_source": "user|time_inferred|default"', envelope)
        self.assertIn("`business.stage` 仍要结构化，但不是 `onion-direction` 的用户必填项", envelope)
        self.assertIn("可以保留为非结构化原料", envelope)
        self.assertIn("每个 skill 只校验自己负责的切片", envelope)
        self.assertIn("交接契约", envelope)
        self.assertIn("统一 Input Envelope", readme)

        for skill_path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md"):
            text = skill_path.read_text(encoding="utf-8")
            self.assertIn("../../shared/references/input-envelope.md", text, skill_path)

    def test_direction_selection_and_stage_contracts_are_explicit(self):
        text = (PLUGIN_ROOT / "skills" / "onion-direction" / "SKILL.md").read_text(encoding="utf-8")
        evals = json.loads((PLUGIN_ROOT / "skills" / "onion-direction" / "evals" / "evals.json").read_text(encoding="utf-8"))

        self.assertIn("关键输入", text)
        self.assertIn("功能 + 卖点", text)
        self.assertIn("缺 `适配阶段` 不反问", text)
        self.assertIn("按当前日期推断", text)
        self.assertIn("候选方向展示时必须显式显示 `适配阶段`", text)
        self.assertIn("不能写省略号", text)
        self.assertIn("不能写“同上”", text)
        self.assertIn("选择第 N 条 / 方向一 / 就用这个", text)
        self.assertIn("先只把被选中的方向写入 Base", text)
        self.assertIn("入库后必须问下一步", text)
        self.assertIn("一次选择多个方向", text)
        self.assertIn("默认创建新版", text)
        self.assertIn("不覆盖原记录", text)
        self.assertIn("明确说废弃原记录", text)
        update_eval = next(item for item in evals["evals"] if item["name"] == "direction-id-edit-creates-new-version")
        self.assertIn("创建一条新版方向", update_eval["expected_output"])
        self.assertIn("不覆盖 D-007 原记录", update_eval["expected_output"])
        missing_eval = next(item for item in evals["evals"] if item["name"] == "direction-missing-required-inputs")
        self.assertIn("只问功能和卖点", missing_eval["expected_output"])
        self.assertNotIn("只问功能和适配阶段", missing_eval["expected_output"])

    def test_copy_missing_channel_and_form_must_ask(self):
        text = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")
        evals = json.loads((PLUGIN_ROOT / "skills" / "onion-copy" / "evals" / "evals.json").read_text(encoding="utf-8"))

        self.assertIn("缺任一项就问，不默认信息流或单图", text)
        self.assertIn("不能因为上文示例或模型偏好默认成信息流", text)
        self.assertIn("先只把被选中的文案写入 Base", text)
        self.assertIn("不要立刻写入", text)
        self.assertIn("入库、基于它出图，还是继续改文案", text)
        self.assertIn("默认创建新版", text)
        self.assertIn("不覆盖原文案", text)
        self.assertIn("明确说废弃原文案", text)
        self.assertIn("文案类型/角度", text)
        self.assertIn("不在用户候选回复里展示", text)
        update_eval = next(item for item in evals["evals"] if item["name"] == "copy-id-edit-creates-new-version")
        self.assertIn("创建一条新版文案", update_eval["expected_output"])
        self.assertIn("不覆盖 C-012 原记录", update_eval["expected_output"])

    def test_candidate_response_format_contracts_are_explicit(self):
        text = (PLUGIN_ROOT / "shared" / "references" / "response-format.md").read_text(encoding="utf-8")

        self.assertIn("方向候选固定排版", text)
        self.assertIn("一张 Markdown 表格", text)
        self.assertIn("| 编号 | 素材方向 | 功能 | 卖点 | 目标人群 | 适配阶段 | 具体场景问题 | 惊艳解法 | 场景奇效 |", text)
        self.assertIn("9 列都必须出现", text)
        self.assertIn("表格后只补一句操作提示", text)
        self.assertIn("不能写省略号", text)
        self.assertIn("不能写“同上”", text)
        self.assertIn("文案候选固定排版", text)
        self.assertIn("生成范围表", text)
        self.assertIn("只列本次请求涉及的合法组合", text)
        self.assertIn("| 渠道/形式 | 单图 | 双图 | 三图 |", text)
        self.assertIn("应用商店 / 学习机 · 单图", text)
        self.assertIn("编号全局唯一", text)
        self.assertIn("展示是 12 条", text)
        self.assertIn("Base 写 14 条", text)
        self.assertIn("拆成 2 条 records", text)
        self.assertIn("| 编号 | 主标题 | 副标题 |", text)
        self.assertIn("| 编号 | 短句1 | 短句2 | 短句3 |", text)
        self.assertNotIn("推荐用图", text)
        copy_section = text.split("## 文案候选固定排版", 1)[1]
        self.assertNotIn("角度：", copy_section)

    def test_execution_policy_splits_fast_gate_and_creative_paths(self):
        text = (PLUGIN_ROOT / "shared" / "references" / "execution-policy.md").read_text(encoding="utf-8")

        self.assertIn("Fast Path", text)
        self.assertIn("Gate Path", text)
        self.assertIn("Creative Path", text)
        self.assertIn("ID 回查、环境检查、状态查询、压缩、打包、Base 写入", text)
        self.assertIn("缺功能/卖点", text)
        self.assertIn("图片角色不明", text)
        self.assertIn("方向生成、文案生成、图片 prompt 生成、批量多样性设计", text)

        for skill_name in ("onion-direction", "onion-copy", "onion-image", "onion-image-iterate"):
            skill = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("../../shared/references/execution-policy.md", skill, skill_name)

    def test_creative_brief_reference_exists_and_is_progressive(self):
        path = PLUGIN_ROOT / "shared" / "references" / "creative-brief.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")

        self.assertIn("渐进式工作记忆", text)
        self.assertIn("不是用户必填表单", text)
        self.assertIn("不是 Base 字段", text)
        self.assertIn("功能事实 → 目标用户 → 具体场景 → 用户阻碍/情绪 → 产品动作 → 可感知变化", text)
        self.assertIn("只服务创意生成和跨 skill 心智继承", text)
        self.assertIn("不服务机械流程", text)
        self.assertIn("产品动作不清楚", text)
        self.assertIn("先查知识库", text)
        self.assertIn("仍不清楚就追问", text)
        self.assertIn("学生视角不是强制第一人称", text)
        self.assertIn("不能为了共鸣编功能", text)

    def test_input_envelope_defines_optional_creative_brief(self):
        text = (PLUGIN_ROOT / "shared" / "references" / "input-envelope.md").read_text(encoding="utf-8")

        self.assertIn('"creative_brief"', text)
        self.assertIn('"level": "full|lite|unknown"', text)
        self.assertIn("Agent 内部交接结构", text)
        self.assertIn("不要求用户填写", text)
        self.assertIn("不一定写 Base", text)
        self.assertIn("关键功能事实缺失", text)

    def test_core_skills_reference_creative_brief(self):
        for skill_name in ("onion-direction", "onion-copy", "onion-image", "onion-image-iterate"):
            text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("../../shared/references/creative-brief.md", text, skill_name)

    def test_creative_brief_keeps_copy_function_grounded(self):
        copy_skill = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")
        channel = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "渠道.md").read_text(encoding="utf-8")
        fields = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "字段定义-文案.md").read_text(encoding="utf-8")
        mistakes = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "常见误区.md").read_text(encoding="utf-8")

        self.assertIn("功能 × 用户", copy_skill)
        self.assertIn("学生视角不是强制第一人称", copy_skill)
        self.assertIn("产品动作不清楚时先查知识库或追问", copy_skill)
        self.assertIn("不能为了共鸣编功能", copy_skill)
        self.assertIn("具体场景 + 具体情绪 + 产品动作 + 可感知变化", channel)
        self.assertIn("具体场景 + 具体情绪 + 产品动作 + 可感知变化", fields)
        self.assertIn("把拍题精学的作业卡题场景套到私教班", mistakes)
        self.assertIn("为了共鸣而编功能", mistakes)

    def test_image_and_iterate_use_brief_without_blocking_mechanical_paths(self):
        image = (PLUGIN_ROOT / "skills" / "onion-image" / "SKILL.md").read_text(encoding="utf-8")
        iterate = (PLUGIN_ROOT / "skills" / "onion-image-iterate" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("视觉化 Creative Brief", image)
        self.assertIn("配置、压缩、打包、Base 写入、状态查询不需要 Creative Brief", image)
        self.assertIn("纯视觉微调不强制补全功能事实", iterate)
        self.assertIn("换卖点、换功能、换文案", iterate)

    def test_copy_quality_guardrails_include_real_bad_phrases(self):
        fields = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "字段定义-文案.md").read_text(encoding="utf-8")
        mistakes = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "常见误区.md").read_text(encoding="utf-8")

        self.assertIn("洋葱不懂还能继续问", fields)
        self.assertIn("洋葱一拍，解析秒出", fields)
        self.assertIn("看不懂，再问洋葱 AI", fields)
        self.assertIn("主语自检", mistakes)

    def test_copy_defaults_to_student_view_and_product_action(self):
        skill = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")
        channel = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "渠道.md").read_text(encoding="utf-8")
        spec = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "规格.md").read_text(encoding="utf-8")
        fields = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "字段定义-文案.md").read_text(encoding="utf-8")
        mistakes = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "常见误区.md").read_text(encoding="utf-8")
        response = (PLUGIN_ROOT / "shared" / "references" / "response-format.md").read_text(encoding="utf-8")

        for text in (skill, channel, spec, fields, mistakes):
            self.assertIn("默认学生视角", text)
            self.assertIn("产品动作", text)
        self.assertIn("功能 × 用户", spec)
        self.assertIn("洋葱一拍", fields)
        self.assertIn("洋葱拍题精学", fields)
        self.assertIn("应用商店 / 学习机 · 单图", response)

    def test_copy_three_image_relationship_library_is_not_single_template(self):
        spec = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "规格.md").read_text(encoding="utf-8")
        fields = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "字段定义-文案.md").read_text(encoding="utf-8")
        channel = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "渠道.md").read_text(encoding="utf-8")
        skill = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")

        for text in (spec, fields, channel):
            self.assertIn("三图关系库", text)
            self.assertIn("痛点 → 解法 → 奇效", text)
            self.assertIn("旧方式 → 新方式 → 反差结果", text)
            self.assertIn("递进排比", text)
            self.assertIn("问题 → 问题 → 统一解法", text)
            self.assertIn("期末冲刺课表", text)
            self.assertIn("不是让你更努力，而是帮你学得更准", text)

        self.assertIn("不要把 `痛点 → 解法 → 奇效` 当成唯一默认结构", skill)

    def test_copy_learning_device_is_single_only_and_app_store_keeps_multi_image(self):
        skill = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")
        channel = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "渠道.md").read_text(encoding="utf-8")
        fields = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "字段定义-文案.md").read_text(encoding="utf-8")

        for text in (skill, channel, fields):
            self.assertIn("学习机只支持单图", text)
            self.assertNotIn("学习机双图", text)
            self.assertNotIn("学习机三图", text)
            self.assertNotIn("应用商店/学习机双图", text)
            self.assertNotIn("应用商店/学习机三图", text)
            self.assertNotIn("学习机用学生视角", text)
            self.assertNotIn("学习机默认学生本人视角", text)
        self.assertIn("应用商店双图", channel)
        self.assertIn("应用商店三图", channel)

    def test_copy_multi_channel_output_groups_shared_single_image_copy(self):
        skill = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")
        response = (PLUGIN_ROOT / "shared" / "references" / "response-format.md").read_text(encoding="utf-8")
        evals = json.loads((PLUGIN_ROOT / "skills" / "onion-copy" / "evals" / "evals.json").read_text(encoding="utf-8"))

        for text in (skill, response):
            self.assertIn("仅当用户同时要求应用商店和学习机单图", text)
            self.assertIn("应用商店单图和学习机单图合并展示", text)
            self.assertIn("先做合法组合过滤", text)
            self.assertIn("生成范围表", text)
            self.assertIn("编号全局唯一", text)
            self.assertIn("用户只要求学习机单图", text)
            self.assertIn("用户只要求应用商店单图", text)
            self.assertIn("如果用户要求两个渠道都入库", text)

        eval_names = {item["name"]: item for item in evals["evals"]}
        self.assertIn("selected-direction-all-channels-all-forms-shared-single", eval_names)
        expected = eval_names["selected-direction-all-channels-all-forms-shared-single"]["expected_output"]
        self.assertIn("应用商店 / 学习机 · 单图", expected)
        self.assertIn("展示 12 条", expected)
        self.assertIn("Base 写 14 条", expected)

    def test_copy_reference_examples_do_not_use_legacy_candidate_layout(self):
        channel = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "渠道.md").read_text(encoding="utf-8")
        manual = (PLUGIN_ROOT / "tests" / "manual-test-cases.md").read_text(encoding="utf-8")

        for text in (channel, manual):
            self.assertNotIn("文案 1｜", text)
            self.assertNotIn("关联方向：", text)
        self.assertIn("| 编号 | 主标题 | 副标题 |", channel)
        self.assertIn("| 编号 | 主标题 | 副标题 |", manual)

    def test_private_tutor_course_knowledge_is_available(self):
        knowledge = PLUGIN_ROOT / "shared" / "knowledge" / "功能-洋葱私教班.md"
        self.assertTrue(knowledge.exists())
        text = knowledge.read_text(encoding="utf-8")
        selling_points = (PLUGIN_ROOT / "shared" / "knowledge" / "卖点库.md").read_text(encoding="utf-8")
        business = (PLUGIN_ROOT / "shared" / "references" / "business-knowledge.md").read_text(encoding="utf-8")
        copy_skill = (PLUGIN_ROOT / "skills" / "onion-copy" / "SKILL.md").read_text(encoding="utf-8")
        direction_skill = (PLUGIN_ROOT / "skills" / "onion-direction" / "SKILL.md").read_text(encoding="utf-8")
        stage = (PLUGIN_ROOT / "skills" / "onion-direction" / "references" / "时间节点策略.md").read_text(encoding="utf-8")
        schema = (PLUGIN_ROOT / "shared" / "base_schema.md").read_text(encoding="utf-8")

        self.assertIn("洋葱私教班", text)
        self.assertIn("面向人群：学生", text)
        self.assertIn("应用商店信息流", text)
        self.assertIn("AI入学诊断", text)
        self.assertIn("30分钟沉浸课堂", text)
        self.assertIn("AI快速解答 + 真人深度辅导", text)
        self.assertIn("期末逆袭计划", text)
        self.assertIn("定制备考方案", text)
        self.assertIn("不是课程包，而是提分方案", text)
        self.assertIn("| F017 | 洋葱私教班 |", selling_points)
        self.assertIn("推荐入库功能名", selling_points)
        self.assertIn("洋葱私教班 |", selling_points)
        self.assertIn("期末前 | 洋葱私教班", selling_points)
        self.assertIn("洋葱私教班", schema)
        self.assertIn("洋葱私教班", direction_skill)
        self.assertIn("洋葱私教班", stage)
        self.assertIn("功能-洋葱私教班.md", business)
        self.assertIn("功能-洋葱私教班.md", copy_skill)

    def test_image_visual_config_preview_and_write_contracts_are_explicit(self):
        text = (PLUGIN_ROOT / "skills" / "onion-image" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("未指定 Logo、CTA 或 IP", text)
        self.assertIn("不要直接默认信息流竖版", text)
        self.assertIn("确认 `LAOZHANG_API_KEY` 存在且不是占位符", text)
        self.assertIn("成图后必须进入 `templates/image-selection.html` 选择页", text)
        self.assertIn("先问目标版位", text)
        self.assertIn("目标尺寸、gpt 出图尺寸、KB 上限", text)
        self.assertIn("assets/asset-manifest.json", text)
        self.assertIn("scripts/build_selection_page.py", text)
        self.assertIn("scripts/interactive_server.py", text)
        self.assertIn("templates/image-config.html", text)
        self.assertIn("scripts/image_workflow.py", text)
        self.assertIn("status --request-id", text)
        self.assertIn("needs_config", text)
        self.assertIn("needs_ui_reference_upload", text)
        self.assertIn("ready_to_render", text)
        self.assertIn("needs_selection", text)
        self.assertIn("needs_package", text)
        self.assertIn("ready_to_write_base", text)
        self.assertIn("needs_attachment_resume", text)
        self.assertIn("needs_api_key", text)
        self.assertIn("invalid_config", text)
        self.assertIn("invalid_artifacts", text)
        self.assertIn("image-config-result.json", text)
        self.assertIn("image-selection-result.json", text)
        self.assertIn("版位先选大类", text)
        self.assertIn("已选版位跨大类保留", text)
        self.assertIn("随机 IP", text)
        self.assertIn("render_size", text)
        self.assertIn("target_size", text)
        self.assertIn("范围 1-50", text)
        self.assertIn("Logo 和 IP 必须显示本地资产缩略图", text)
        self.assertIn("字体参考只有启用 / 不启用", text)
        self.assertIn("CTA 按具体版位的 `cta_policy` 显示", text)
        self.assertIn("不在 HTML 里上传", text)
        self.assertIn("不是独立入口", text)
        self.assertIn("手机、平板、电脑、学习机、投影屏、电子屏幕", text)
        self.assertIn("可识别的洋葱 APP/学习界面屏幕内容", text)
        self.assertIn("弱化/模糊屏幕内容", text)
        self.assertIn("screen_ui_reference_required=true", text)
        self.assertIn("ui_reference_required=true", text)
        self.assertIn("必须提醒用户回到 Codex 对话上传截图", text)
        self.assertIn("没有收到截图前不能进入 prompt、validate-only 或 render", text)
        self.assertIn("探索生成", text)
        self.assertIn("同类扩展", text)
        self.assertIn("/api/image-sets", text)
        self.assertIn("accepted_schemes", text)
        self.assertIn("唯一允许写入飞书", text)
        self.assertIn("多组原始文案先整理成 copy_drafts", text)
        self.assertIn("生图前必须有 C-XXX", text)
        self.assertIn("一个 C-XXX 只代表一个渠道 + 一个图片形式", text)
        self.assertIn("预计图组数 = 文案数 × 版位数 × 套数", text)
        self.assertIn("最多 100 图组", text)
        self.assertIn("不要让用户在聊天里回复“选 set1 / 选 set2 / 选第 N 套”", text)
        self.assertIn("优先读取 `image-selection-result.json`", text)
        self.assertIn("提交后告诉我已提交", text)
        self.assertIn("不要让用户粘贴 JSON", text)
        self.assertNotIn("页面复制出的同结构 JSON", text)
        self.assertIn("请在页面完成标注并点击提交", text)
        self.assertIn("scripts/package_accepted_images.py", text)
        self.assertIn("scripts/write_selection_feedback.py", text)
        self.assertIn("固定规则反馈 / 主观感受反馈", text)
        self.assertIn("invalid_selection_feedback", text)
        self.assertIn("feedbacks", text)
        self.assertIn("最终回复必须包含", text)
        self.assertIn("本地图片包路径", text)
        self.assertIn("可点击 Markdown 本地文件链接", text)
        self.assertIn("打开交付目录", text)
        self.assertIn("package_zip", text)
        self.assertIn("scripts/cleanup_image_outputs.py", text)
        self.assertIn("超过 7 天的原始 PNG", text)
        self.assertIn("先配置页，后标注/选择页", text)
        self.assertIn("selection-assets", text)
        self.assertIn("洋葱专属字体参考图", text)
        self.assertIn("默认 200KB", text)
        self.assertIn("图片配置页是所有付费生图的强制入口", text)
        self.assertIn("方向名", text)
        self.assertIn("delivery_name", text)
        self.assertIn("只填方向名，不填文件夹名或图片名", text)
        self.assertIn("方向31.zip", text)
        self.assertIn("不能作为跳过配置页的理由", text)
        self.assertIn("不允许绕过配置页直接生图", text)
        self.assertIn("不允许调用聊天内置 imagegen", text)
        self.assertIn("方向 ID 不是生图锚点", text)
        self.assertIn("转 `onion-copy`", text)
        self.assertIn("用户上传旧图", text)
        self.assertIn("转 `onion-image-iterate`", text)
        self.assertNotIn("方向 ID、刚生成的第 N 条文案或已有文案内容", text)
        self.assertNotIn("用户给 D-XXX 想直接出图时，先回查方向", text)
        self.assertNotIn("完整 brief 不弹配置卡", text)

    def test_image_and_iterate_entry_boundaries_are_explicit(self):
        image = (PLUGIN_ROOT / "skills" / "onion-image" / "SKILL.md").read_text(encoding="utf-8")
        iterate = (PLUGIN_ROOT / "skills" / "onion-image-iterate" / "SKILL.md").read_text(encoding="utf-8")
        image_evals = json.loads((PLUGIN_ROOT / "skills" / "onion-image" / "evals" / "evals.json").read_text(encoding="utf-8"))
        channel_doc = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "渠道与版位.md").read_text(encoding="utf-8")
        size_doc = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "版位比例与尺寸.md").read_text(encoding="utf-8")
        export_doc = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "压缩与导出.md").read_text(encoding="utf-8")
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("只给 D-XXX / 方向 ID", image)
        self.assertIn("不进入本 skill 的生图流程", image)
        self.assertIn("G-XXX、用户上传旧图", image)
        self.assertIn("扩同类、换文案、换角色", image)
        self.assertIn("转 `onion-image-iterate`", image)
        self.assertIn("用户上传旧图", iterate)
        self.assertIn("换文案、换角色、扩同类", iterate)
        self.assertIn("如果要新增或替换可识别的洋葱 APP/学习界面屏幕内容", iterate)
        self.assertIn("上传图如果只是 APP 截图、风格参考图或 IP 参考图", image)
        self.assertIn("只有用户把上传图当作旧广告图锚点", image)
        self.assertIn("成图后仍必须进入选择页", iterate)
        self.assertIn("accepted_schemes", iterate)
        self.assertIn("image_workflow.py", iterate)
        self.assertIn("needs_selection", iterate)
        self.assertIn("needs_package", iterate)
        self.assertIn("ready_to_write_base", iterate)
        self.assertIn("needs_attachment_resume", iterate)
        self.assertIn("--write-result", iterate)
        self.assertIn("package_accepted_images.py", iterate)
        self.assertIn("父图组", iterate)
        self.assertIn("打开本地交付包", iterate)
        self.assertIn("方向 ID 不能直接跳到图", readme)
        self.assertIn("方向：生成候选 → 用户确认 → 入库", readme)
        self.assertIn("迭代图：确认旧图和改动轴 → 生图 → 选择页标注 → 采纳图入库", readme)

        direction_eval = next(item for item in image_evals["evals"] if item["id"] == 5)
        self.assertIn("不应启动 /image-config", direction_eval["expected_output"])
        self.assertIn("转 onion-copy", direction_eval["expected_output"])
        expansion_eval = next(item for item in image_evals["evals"] if item["id"] == 4)
        self.assertIn("转 onion-image-iterate", expansion_eval["expected_output"])
        upload_eval = next(item for item in image_evals["evals"] if item["id"] == 7)
        self.assertIn("转 onion-image-iterate", upload_eval["expected_output"])
        ui_eval = next(item for item in image_evals["evals"] if item["id"] == 17)
        self.assertIn("screen_ui_reference_required=true", ui_eval["expected_output"])
        self.assertIn("ui_reference_required=true", ui_eval["expected_output"])
        self.assertIn("先提醒用户在 Codex 对话上传截图", ui_eval["expected_output"])
        self.assertIn("不能进入 render.py", ui_eval["expected_output"])
        ref_eval = next(item for item in image_evals["evals"] if item["name"] == "uploaded-reference-image-stays-in-image-skill")
        self.assertIn("参考素材", ref_eval["expected_output"])
        self.assertIn("仍走 onion-image", ref_eval["expected_output"])
        iterate_evals = json.loads((PLUGIN_ROOT / "skills" / "onion-image-iterate" / "evals" / "evals.json").read_text(encoding="utf-8"))
        accepted_eval = next(item for item in iterate_evals["evals"] if item["name"] == "iterate-result-must-use-selection-page-before-base")
        self.assertIn("选择页", accepted_eval["expected_output"])
        self.assertIn("accepted_schemes", accepted_eval["expected_output"])
        self.assertIn("父图组", accepted_eval["expected_output"])

        self.assertNotIn("image_count=1", channel_doc)
        self.assertNotIn("双图、三图、组图先置灰", channel_doc)
        self.assertNotIn("双图 / 三图 / 组图：后续", size_doc)
        self.assertNotIn("双图 / 三图 / 组图 | 一期置灰", export_doc)

    def test_image_iteration_asks_when_upload_role_or_intent_is_unclear(self):
        using = (PLUGIN_ROOT / "skills" / "onion-using" / "SKILL.md").read_text(encoding="utf-8")
        image = (PLUGIN_ROOT / "skills" / "onion-image" / "SKILL.md").read_text(encoding="utf-8")
        iterate = (PLUGIN_ROOT / "skills" / "onion-image-iterate" / "SKILL.md").read_text(encoding="utf-8")
        envelope = (PLUGIN_ROOT / "shared" / "references" / "input-envelope.md").read_text(encoding="utf-8")
        runtime = (PLUGIN_ROOT / "shared" / "references" / "runtime-adapters.md").read_text(encoding="utf-8")
        iterate_evals = json.loads((PLUGIN_ROOT / "skills" / "onion-image-iterate" / "evals" / "evals.json").read_text(encoding="utf-8"))
        critical = json.loads((PLUGIN_ROOT / "behavior-evals" / "critical-flows.json").read_text(encoding="utf-8"))

        self.assertIn("正确优先于少问", using)
        self.assertIn("有一点不清楚就追问", using)
        self.assertIn("uploaded_image_role", envelope)
        self.assertIn("owned_old_ad|competitor_reference|layout_reference|style_reference|ip_reference|screen_ui_reference|unknown", envelope)
        self.assertIn("图片角色不明时必须追问", runtime)
        self.assertIn("不要靠是否有文案判断", image)
        self.assertIn("竞品/外部参考图", image)
        self.assertIn("不写 `父图组`", image)

        self.assertIn("继承型配置卡", iterate)
        self.assertIn("小改一下 / 同类多来几套 / 换形式重做", iterate)
        self.assertIn("一套图只有一份主配置", iterate)
        self.assertIn("传三张图不等于三份配置", iterate)
        self.assertIn("竞品/外部参考图不能当父图组", iterate)
        self.assertIn("generation_mode=iterate", iterate)
        self.assertIn("iteration_mode=tweak|expand_similar|reframe", iterate)

        eval_names = {item["name"]: item for item in iterate_evals["evals"]}
        self.assertIn("ambiguous-upload-role-asks-before-routing", eval_names)
        self.assertIn("competitor-reference-does-not-write-parent-group", eval_names)
        self.assertIn("three-image-set-expands-with-one-main-config", eval_names)
        self.assertIn("继承型配置卡", eval_names["three-image-set-expands-with-one-main-config"]["expected_output"])

        critical_cases = {item["id"]: item for item in critical["evals"]}
        self.assertIn("ambiguous-upload-role-must-ask", critical_cases)
        self.assertIn("competitor-layout-reference-not-parent", critical_cases)

    def test_image_default_font_is_not_blocking(self):
        skill = (PLUGIN_ROOT / "skills" / "onion-image" / "SKILL.md").read_text(encoding="utf-8")
        visual = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "视觉元素规范.md").read_text(encoding="utf-8")
        single = (PLUGIN_ROOT / "shared" / "recipes" / "single-prompt.md").read_text(encoding="utf-8")
        base = (PLUGIN_ROOT / "shared" / "recipes" / "base-prompt.md").read_text(encoding="utf-8")

        self.assertIn("字体不是阻塞项", skill)
        self.assertIn("随机/轮换选 1 张", visual)
        self.assertIn("不要求 100% 复刻", skill)
        self.assertIn("不复制参考图里的示例文字", visual)
        self.assertIn("default font is an Onion font reference image", single)
        self.assertIn("Default font still uses an Onion font reference image", base)

    def test_no_ip_prompts_randomize_visual_style(self):
        visual = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "视觉元素规范.md").read_text(encoding="utf-8")
        single = (PLUGIN_ROOT / "shared" / "recipes" / "single-prompt.md").read_text(encoding="utf-8")
        base = (PLUGIN_ROOT / "shared" / "recipes" / "base-prompt.md").read_text(encoding="utf-8")
        batch = (PLUGIN_ROOT / "shared" / "recipes" / "batch-prompting.md").read_text(encoding="utf-8")

        self.assertIn("有 IP 时", visual)
        self.assertIn("无 IP 时", visual)
        self.assertIn("高质量动漫插画", visual)
        self.assertIn("毛毡手作", visual)
        self.assertIn("半写实广告插画", visual)
        self.assertIn("赛璐珞动漫", visual)
        self.assertIn("高质量家庭动画电影感", visual)
        self.assertIn("不要写第三方品牌风格名", visual)

        self.assertIn("有 IP 时", single)
        self.assertIn("无 IP 时", single)
        self.assertIn("从视觉风格池随机选择", single)
        self.assertIn("有 IP 时", base)
        self.assertIn("无 IP 时", base)
        self.assertIn("从视觉风格池随机选择", base)
        self.assertIn("used_styles", batch)
        self.assertIn("Style", batch)

    def test_prompt_recipes_respect_screen_ui_gate(self):
        single = (PLUGIN_ROOT / "shared" / "recipes" / "single-prompt.md").read_text(encoding="utf-8")
        base = (PLUGIN_ROOT / "shared" / "recipes" / "base-prompt.md").read_text(encoding="utf-8")
        branch = (PLUGIN_ROOT / "shared" / "recipes" / "branch-prompt.md").read_text(encoding="utf-8")

        for text in (single, base, branch):
            self.assertIn("有真实截图时", text)
            self.assertIn("没有真实截图时", text)
            self.assertIn("弱化/模糊屏幕", text)
        self.assertIn("不要编造可识别的洋葱 APP 界面", single)
        self.assertIn("screen_ui_reference_required=true", base)
        self.assertIn("新增或替换屏幕内容", branch)

    def test_prompt_recipes_keep_size_rules_out_of_prompt_text(self):
        single = (PLUGIN_ROOT / "shared" / "recipes" / "single-prompt.md").read_text(encoding="utf-8")
        base = (PLUGIN_ROOT / "shared" / "recipes" / "base-prompt.md").read_text(encoding="utf-8")

        for text in (single, base):
            self.assertIn("Prompt 正文不写具体像素", text)
            self.assertIn("render.py --size", text)
            self.assertIn("只保留竖版 / 横版 / 方图等构图语境", text)
            self.assertNotIn("竖版 9:16", text)
            self.assertNotIn("横版 3:2", text)
            self.assertNotRegex(text, r"\\d{3,4}x\\d{3,4}.*prompt")

    def test_new_teacher_ip_assets_are_documented(self):
        visual = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "视觉元素规范.md").read_text(encoding="utf-8")
        naming = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "资产命名与参考图标注.md").read_text(encoding="utf-8")

        self.assertIn("张无限老师", visual)
        self.assertIn("文心老师", visual)
        self.assertIn("Nina老师", visual)
        self.assertIn("ip.zhangwuxian.teacher.fullbody.001", visual)
        self.assertIn("ip.wenxin.teacher.fullbody.001", visual)
        self.assertIn("ip.nina.teacher.fullbody.001", visual)
        self.assertIn("stage=teacher", naming)
        self.assertNotIn("文思老师", visual)

    def test_image_export_docs_include_zip_and_cleanup_policy(self):
        text = (PLUGIN_ROOT / "skills" / "onion-image" / "references" / "压缩与导出.md").read_text(encoding="utf-8")

        self.assertIn("采纳图打 zip", text)
        self.assertIn("package_accepted_images.py", text)
        self.assertIn("accepted_schemes", text)
        self.assertIn("zip 只包含采纳图片", text)
        self.assertIn("<zip-stem>-manifest.json", text)
        self.assertIn("<方向名>.zip", text)
        self.assertIn("<方向名>-<大类>-<渠道>-<版位>/<方向名>-<大类>-<渠道>-<版位>-<序号>.jpg", text)
        self.assertIn("Base 仍靠 request_id、copy_id、set_id、manifest 追溯", text)
        self.assertIn("原始 PNG 保留 7 天", text)
        self.assertIn("cleanup_image_outputs.py", text)
        self.assertIn("50 套三图", text)

    def test_runtime_adapter_has_non_modal_choice_fallback(self):
        text = (PLUGIN_ROOT / "shared" / "references" / "runtime-adapters.md").read_text(encoding="utf-8")

        self.assertIn("Do not rely on modal popups", text)
        self.assertIn("local HTML interaction page", text)
        self.assertIn("image-config-result.json", text)
        self.assertIn("image-sets.json", text)
        self.assertIn("mandatory for every paid image request", text)
        self.assertIn("cannot skip the config page", text)
        self.assertIn("explicit numbered or named options", text)
        self.assertIn("Copy selected", text)

    def test_help_documents_one_click_setup_and_cross_platform_check(self):
        help_skill = (PLUGIN_ROOT / "skills" / "onion-help" / "SKILL.md").read_text(encoding="utf-8")
        checklist = (PLUGIN_ROOT / "skills" / "onion-help" / "references" / "环境自检清单.md").read_text(encoding="utf-8")
        env_template = (PLUGIN_ROOT / ".env.template").read_text(encoding="utf-8")

        self.assertIn("一键配置", help_skill)
        self.assertIn("setup_wizard.py ensure", help_skill)
        self.assertIn("Mac / Windows", help_skill)
        self.assertIn("setup-status.json", help_skill)
        self.assertIn("usage-state.json", help_skill)
        self.assertIn("update-status.json", help_skill)
        self.assertIn("ONION_PLUGIN_AUTO_UPDATE=0", help_skill)
        self.assertIn("safe ensure/bootstrap", help_skill)
        self.assertIn("platform.family", checklist)
        self.assertIn("checks.plugin_update", checklist)
        self.assertIn("24 小时", checklist)
        self.assertIn("ONION_PLUGIN_AUTO_UPDATE=0", checklist)
        self.assertIn("python3 skills/onion-help/scripts/setup_wizard.py ensure", checklist)
        self.assertIn("python3 skills/onion-help/scripts/setup_wizard.py update-check", checklist)
        self.assertIn("python3 skills/onion-help/scripts/setup_wizard.py update", checklist)
        self.assertIn("ONION_AD_OUTPUT_ROOT", checklist)
        self.assertNotIn("which lark-cli", checklist)
        self.assertNotIn("source ~/.onion-ad/.env", checklist)
        self.assertIn("Windows", env_template)

    def test_core_skills_require_lightweight_first_use_readiness_check(self):
        for skill_name in ("onion-using", "onion-direction", "onion-copy", "onion-image", "onion-image-iterate"):
            text = (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("首启环境门禁", text, skill_name)
            self.assertIn("setup-status.json", text, skill_name)
            self.assertIn("usage-state.json", text, skill_name)
            self.assertIn("update-status.json", text, skill_name)
            self.assertIn("24 小时", text, skill_name)
            self.assertIn("onion-help", text, skill_name)

    def test_image_batch_render_and_laozhang_limits_are_documented(self):
        image = (PLUGIN_ROOT / "skills" / "onion-image" / "SKILL.md").read_text(encoding="utf-8")
        iterate = (PLUGIN_ROOT / "skills" / "onion-image-iterate" / "SKILL.md").read_text(encoding="utf-8")
        env_template = (PLUGIN_ROOT / ".env.template").read_text(encoding="utf-8")
        checklist = (PLUGIN_ROOT / "skills" / "onion-help" / "references" / "环境自检清单.md").read_text(encoding="utf-8")
        recipe = (PLUGIN_ROOT / "shared" / "recipes" / "render-chain.md").read_text(encoding="utf-8")

        for text in (image, iterate):
            self.assertIn("batch_render.py", text)
            self.assertIn("并发单位是 render job", text)
            self.assertIn("不是套数", text)
            self.assertIn("默认 6", text)
            self.assertIn("降到 3", text)
            self.assertIn("100 concurrent requests", text)
            self.assertIn("双图/三图链式依赖", text)
            self.assertIn("不要手工并发多个 render.py", text)
        self.assertIn("ONION_IMAGE_CONCURRENCY=6", env_template)
        self.assertIn("ONION_IMAGE_FALLBACK_CONCURRENCY=3", env_template)
        self.assertIn("GPTImage2 Enterprise", checklist)
        self.assertIn("3000 RPM", checklist)
        self.assertIn("100 concurrent requests", checklist)
        self.assertIn("batch_render.py", recipe)
        self.assertIn("ONION_IMAGE_CONCURRENCY", recipe)


if __name__ == "__main__":
    unittest.main()
