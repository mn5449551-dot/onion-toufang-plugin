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
        self.assertNotIn("下次启动 skill 自动补", text)

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

    def test_router_skill_defines_top_level_dispatch_rules(self):
        text = (PLUGIN_ROOT / "skills" / "onion-router" / "SKILL.md").read_text(encoding="utf-8")
        evals = json.loads((PLUGIN_ROOT / "skills" / "onion-router" / "evals" / "evals.json").read_text(encoding="utf-8"))
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("只负责分流", text)
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
        self.assertIn("onion-router", readme)

        cases = {item["name"]: item["expected_output"] for item in evals["evals"]}
        self.assertIn("D-XXX 不能直接出图", cases["direction-id-image-request-routes-to-copy"])
        self.assertIn("仍走 onion-image", cases["uploaded-reference-image-does-not-route-to-iterate"])
        self.assertIn("onion-image-iterate", cases["uploaded-old-ad-routes-to-iterate"])
        self.assertIn("不能口头选择 set", cases["oral-image-selection-routes-to-selection-page-result"])

    def test_direction_selection_and_stage_contracts_are_explicit(self):
        text = (PLUGIN_ROOT / "skills" / "onion-direction" / "SKILL.md").read_text(encoding="utf-8")
        evals = json.loads((PLUGIN_ROOT / "skills" / "onion-direction" / "evals" / "evals.json").read_text(encoding="utf-8"))

        self.assertIn("候选方向展示时必须显式显示 `适配阶段`", text)
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
        update_eval = next(item for item in evals["evals"] if item["name"] == "copy-id-edit-creates-new-version")
        self.assertIn("创建一条新版文案", update_eval["expected_output"])
        self.assertIn("不覆盖 C-012 原记录", update_eval["expected_output"])

    def test_copy_quality_guardrails_include_real_bad_phrases(self):
        fields = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "字段定义-文案.md").read_text(encoding="utf-8")
        mistakes = (PLUGIN_ROOT / "skills" / "onion-copy" / "references" / "常见误区.md").read_text(encoding="utf-8")

        self.assertIn("洋葱不懂还能继续问", fields)
        self.assertIn("洋葱一拍，解析秒出", fields)
        self.assertIn("看不懂，再问洋葱 AI", fields)
        self.assertIn("主语自检", mistakes)

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
        self.assertIn("scripts/image_workflow.py", text)
        self.assertIn("status --request-id", text)
        self.assertIn("needs_config", text)
        self.assertIn("needs_ui_reference_upload", text)
        self.assertIn("ready_to_render", text)
        self.assertIn("needs_selection", text)
        self.assertIn("needs_package", text)
        self.assertIn("ready_to_write_base", text)
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
        self.assertIn("不要让用户在聊天里回复“选 set1 / 选 set2 / 选第 N 套”", text)
        self.assertIn("优先读取 `image-selection-result.json`", text)
        self.assertIn("页面复制出的同结构 JSON", text)
        self.assertIn("请在页面完成标注并点击提交", text)
        self.assertIn("scripts/package_accepted_images.py", text)
        self.assertIn("scripts/cleanup_image_outputs.py", text)
        self.assertIn("超过 7 天的原始 PNG", text)
        self.assertIn("先配置页，后标注/选择页", text)
        self.assertIn("selection-assets", text)
        self.assertIn("洋葱专属字体参考图", text)
        self.assertIn("默认 200KB", text)
        self.assertIn("图片配置页是所有付费生图的强制入口", text)
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
        self.assertIn("package_accepted_images.py", iterate)
        self.assertIn("父图组", iterate)
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


if __name__ == "__main__":
    unittest.main()
