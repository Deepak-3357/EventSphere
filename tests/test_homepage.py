"""Regression checks for the production homepage shell and data wiring."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "frontend" / "index.html"
APP = ROOT / "frontend" / "assets" / "js" / "app.js"


class HomepageRegressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = HOME.read_text(encoding="utf-8")
        cls.app = APP.read_text(encoding="utf-8")

    def test_homepage_has_real_discovery_sections(self):
        self.assertIn("Discover events.", self.home)
        self.assertIn('id="featuredEvents"', self.home)
        self.assertIn('id="categoryGrid"', self.home)
        self.assertIn('id="how-it-works"', self.home)
        self.assertNotIn("Phase 3 authentication", self.home)
        self.assertNotIn("Coming soon", self.home)
        self.assertNotIn("Event discovery will be here", self.home)
        self.assertNotIn("apiStatusButton", self.home)

    def test_homepage_uses_bounded_public_catalog_requests(self):
        self.assertIn('apiUrl("/api/events?status=published&limit=6")', self.app)
        self.assertIn('apiUrl("/api/categories")', self.app)
        self.assertIn("withTimeout", self.app)
        self.assertIn("retryEvents", self.app)

    def test_homepage_scripts_are_deferred_without_bootstrap_bundle(self):
        self.assertIn('src="assets/js/app.js" defer', self.home)
        self.assertNotIn("bootstrap.bundle.min.js", self.home)
        self.assertIn('loading="lazy"', self.app)


if __name__ == "__main__":
    unittest.main()
