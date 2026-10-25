from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "scripts"))
from validate_site import Page, script_errors, validate


SCRIPT = '<script src="/assets/theme.js"></script>'
CONTROL = """<div data-theme-settings hidden>
<button type="button" data-theme-control value="system" aria-label="Theme: system; switch to light"></button>
<span data-theme-status role="status" hidden>Not saved.</span></div>"""


def html(script=SCRIPT, control=CONTROL, body=""):
    return (
        '<!doctype html><html lang="zh-CN"><head><meta name="viewport" content="width=device-width">'
        f"<title>Theme fixture</title>{script}</head><body><main><h1>Theme fixture</h1>"
        f"{control}{body}</main></body></html>"
    )


class SiteThemeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def parse(self, content):
        path = self.root / "fixture.html"
        path.write_text(content, encoding="utf-8")
        return Page(path)

    def test_one_local_head_script_and_hidden_theme_button_are_allowed(self):
        self.assertEqual(script_errors(self.parse(html())), [])

    def test_other_scripts_inline_code_duplicate_attributes_and_extra_permissions_are_rejected(self):
        scripts = [
            "", '<script>alert(1)</script>',
            '<script src="https://example.com/theme.js"></script>',
            '<script src="/assets/other.js"></script>',
            '<script src="/assets/theme.js?other"></script>',
            '<script src="/assets/theme.js">alert(1)</script>',
            '<script src="/assets/theme.js" src="https://example.com/other.js"></script>',
            '<script src="/assets/theme.js" defer></script>',
            '<script src="/assets/theme.js" onload="alert(1)"></script>',
            '<script src="/assets/theme.js"/>',
            SCRIPT + SCRIPT,
        ]
        for script in scripts:
            with self.subTest(script=script):
                self.assertTrue(script_errors(self.parse(html(script=script))))

    def test_approved_script_cannot_be_moved_into_the_body(self):
        errors = script_errors(self.parse(html(script="", body=SCRIPT)))
        self.assertTrue(any("head script" in error for error in errors))

    def test_script_must_be_a_direct_head_child_not_an_inert_nested_script(self):
        modes = {
            "native": Page.CDATA_CONTENT_ELEMENTS,
            "title-as-text": (*Page.CDATA_CONTENT_ELEMENTS, "title"),
        }
        for mode, elements in modes.items():
            with self.subTest(parser=mode), patch.object(Page, "CDATA_CONTENT_ELEMENTS", elements):
                self.assertEqual(script_errors(self.parse(html())), [])
                for wrapper in ("template", "noscript", "title"):
                    with self.subTest(wrapper=wrapper):
                        page = self.parse(html(script=f"<{wrapper}>{SCRIPT}</{wrapper}>"))
                        self.assertFalse(any(script["head"] for script in page.scripts))
                        self.assertTrue(script_errors(page))

    def test_base_element_cannot_redirect_the_approved_root_relative_script(self):
        content = html().replace("<title>", '<base href="https://example.com/"><title>', 1)
        errors = script_errors(self.parse(content))
        self.assertTrue(any("script's origin" in error for error in errors))

    def test_inline_event_handlers_are_rejected_even_with_an_approved_script(self):
        errors = script_errors(self.parse(html(body='<button onclick="alert(1)">Run</button>')))
        self.assertIn("inline event handlers are not allowed", errors)

    def test_missing_visible_duplicate_or_invalid_theme_controls_are_rejected(self):
        for control in ("", CONTROL.replace(" hidden", "", 1), CONTROL + CONTROL,
                        CONTROL.replace('value="system"', 'value="other"'),
                        CONTROL.replace('type="button"', 'type="submit"'),
                        CONTROL.replace('aria-label="Theme: system; switch to light"', ""),
                        f"<nav>{CONTROL}</nav>"):
            with self.subTest(control=control):
                self.assertTrue(script_errors(self.parse(html(control=control))))

    def test_portal_theme_button_is_immediately_before_github_and_outside_navigation(self):
        content = (PROJECT / "site" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(script_errors(self.parse(content)), [])
        self.assertLess(content.index("</nav>"), content.index("data-theme-control"))
        self.assertLess(content.index("data-theme-control"), content.index('class="repo-link"'))

    def test_archives_must_have_neither_scripts_nor_theme_controls(self):
        self.assertEqual(script_errors(self.parse(html(script="", control="")), archived=True), [])
        for script, control in ((SCRIPT, ""), ("", CONTROL), (SCRIPT, CONTROL)):
            with self.subTest(script=script, control=control):
                self.assertTrue(script_errors(self.parse(html(script=script, control=control)), archived=True))

    def fixture_site(self):
        for name in ("index.html", "404.html", "privacy/index.html"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html(), encoding="utf-8")
        for name in ("site.css", "privacy.css", "theme.css", "theme.js", "favicon.svg"):
            path = self.root / "assets" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("", encoding="utf-8")
        (self.root / ".nojekyll").write_text("", encoding="utf-8")

    def test_full_validator_accepts_the_scoped_exception(self):
        self.fixture_site()
        with patch("validate_site.SITE", self.root), patch("validate_site.build_policy"):
            self.assertEqual(validate(), [])

    def test_full_validator_requires_the_imported_theme_styles_and_script(self):
        self.fixture_site()
        for name in ("theme.css", "theme.js"):
            path = self.root / "assets" / name
            path.unlink()
            with self.subTest(name=name), patch("validate_site.SITE", self.root), patch("validate_site.build_policy"):
                self.assertTrue(any("Missing required site file" in error for error in validate()))
            path.write_text("", encoding="utf-8")

    def test_full_validator_still_rejects_other_https_scripts(self):
        self.fixture_site()
        (self.root / "index.html").write_text(
            html(script='<script src="https://example.com/theme.js"></script>'), encoding="utf-8",
        )
        with patch("validate_site.SITE", self.root), patch("validate_site.build_policy"):
            self.assertTrue(any("only an empty head script" in error for error in validate()))


if __name__ == "__main__":
    unittest.main()
