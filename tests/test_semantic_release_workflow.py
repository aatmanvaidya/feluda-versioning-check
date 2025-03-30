import unittest
import os
import tempfile
import shutil
import subprocess
import tomlkit

from scripts.semantic_release_workflow import PackageVersionManager


class TestPackageVersionManager(unittest.TestCase):
    def setUp(self):
        """Set up a temporary directory structure simulating a monorepo with git."""
        # Create a temporary directory for our test repo
        self.temp_dir = tempfile.mkdtemp()

        # Initialize git repo
        self._run_git_command(["git", "init"])
        self._run_git_command(["git", "config", "user.name", "Test User"])
        self._run_git_command(["git", "config", "user.email", "test@example.com"])

        # Create monorepo structure
        self.feluda_dir = os.path.join(self.temp_dir, "feluda")
        self.operators_dir = os.path.join(self.temp_dir, "operators")

        os.makedirs(self.feluda_dir, exist_ok=True)
        os.makedirs(self.operators_dir, exist_ok=True)

        # Create feluda package
        self._create_package_files("feluda", "0.1.0")

        # Create operator packages
        self._create_package_files(os.path.join("operators", "operator1"), "0.1.0")
        self._create_package_files(os.path.join("operators", "operator2"), "0.2.0")

        # Initial commit for all packages
        self._run_git_command(["git", "add", "."])
        self._run_git_command(["git", "commit", "-m", "Initial commit"])
        self.initial_commit = self._get_current_commit()

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)

    def _run_git_command(self, command):
        """Run a git command in the temporary directory."""
        return subprocess.run(
            command, cwd=self.temp_dir, capture_output=True, check=True, text=True
        )

    def _get_current_commit(self):
        """Get the current commit hash."""
        result = self._run_git_command(["git", "rev-parse", "HEAD"])
        return result.stdout.strip()

    def _create_package_files(self, package_path, version):
        """Create a package directory with pyproject.toml."""
        # Determine if this is the root package or a subpackage
        is_root = package_path == "feluda"

        # Set up paths
        if is_root:
            pyproject_path = os.path.join(self.temp_dir, "pyproject.toml")
            package_dir = self.feluda_dir
        else:
            package_dir = os.path.join(self.temp_dir, package_path)
            pyproject_path = os.path.join(package_dir, "pyproject.toml")
            os.makedirs(package_dir, exist_ok=True)

        # Package name (derived from path for simplicity)
        package_name = os.path.basename(package_path)

        # Create pyproject.toml content with structure matching the real one
        pyproject_data = tomlkit.document()

        # Add project section with realistic fields
        project = tomlkit.table()
        project["name"] = package_name
        project["version"] = version
        project["requires-python"] = ">=3.10"

        # Add dependencies
        dependencies = tomlkit.array()
        dependencies.extend(
            [
                "torch>=2.5.1",
                "torchvision>=0.20.1",
                "numpy>=2.2.1",
                "pillow>=11.1.0",
            ]
        )
        project["dependencies"] = dependencies
        pyproject_data["project"] = project

        # Add build-system section
        build_system = tomlkit.table()
        build_system["requires"] = ["hatchling"]
        build_system["build-backend"] = "hatchling.build"
        pyproject_data["build-system"] = build_system

        # Add tool.semantic_release section
        tool = tomlkit.table()
        semantic_release = tomlkit.table()

        # Add version_variable
        version_variable = tomlkit.array()
        version_variable.append("pyproject.toml:project.version")
        semantic_release["version_variable"] = version_variable

        # Add branches.main section
        branches = tomlkit.table()
        main = tomlkit.table()
        main["match"] = "main"
        main["prerelease"] = False
        main["tag_format"] = "{name}-{version}"
        branches["main"] = main
        semantic_release["branches"] = branches
        tool["semantic_release"] = semantic_release
        pyproject_data["tool"] = tool

        # Write to file
        with open(pyproject_path, "w") as f:
            f.write(tomlkit.dumps(pyproject_data))

        # Create a dummy Python file in the package
        with open(os.path.join(package_dir, "__init__.py"), "w") as f:
            f.write(f'"""Package {package_name}."""\n\n__version__ = "{version}"\n')

    def _make_changes_and_commit(self, package_path, commit_msg, file_content=None):
        """Make changes to a package and commit them."""
        # Determine if this is the root package
        is_root = package_path == "feluda"

        # Set up paths
        if is_root:
            package_dir = self.feluda_dir
        else:
            package_dir = os.path.join(self.temp_dir, package_path)

        # Create or modify a file in the package
        if file_content is None:
            file_content = f"# Change in {package_path}\n# {commit_msg}\n"

        change_file = os.path.join(package_dir, "change.py")
        with open(change_file, "w") as f:
            f.write(file_content)

        # Commit the changes
        self._run_git_command(["git", "add", change_file])
        self._run_git_command(["git", "commit", "-m", commit_msg])

        return self._get_current_commit()

    def _get_current_version(self, package_path):
        """Get the current version from pyproject.toml."""
        is_root = package_path == "feluda"

        if is_root:
            pyproject_path = os.path.join(self.temp_dir, "pyproject.toml")
        else:
            pyproject_path = os.path.join(self.temp_dir, package_path, "pyproject.toml")

        with open(pyproject_path, "r") as f:
            pyproject_data = tomlkit.parse(f.read())

        return pyproject_data["project"]["version"]

    def test_package_discovery(self):
        """Test that the class correctly discovers all packages in the monorepo."""
        manager = PackageVersionManager(
            self.temp_dir, self.initial_commit, self.initial_commit
        )

        # Check that all packages were discovered
        self.assertIn("feluda", manager.packages)
        self.assertIn(os.path.join("operators", "operator1"), manager.packages)
        self.assertIn(os.path.join("operators", "operator2"), manager.packages)

        # Verify that package info is correct
        self.assertEqual(manager.packages["feluda"]["current_version"], "0.1.0")
        self.assertEqual(
            manager.packages[os.path.join("operators", "operator1")]["current_version"],
            "0.1.0",
        )
        self.assertEqual(
            manager.packages[os.path.join("operators", "operator2")]["current_version"],
            "0.2.0",
        )


#     def test_parse_conventional_commit(self):
#         """Test the conventional commit parsing logic."""
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, self.initial_commit)

#         # Test different commit types
#         self.assertEqual(manager._parse_conventional_commit("feat: Add new feature"), "minor")
#         self.assertEqual(manager._parse_conventional_commit("fix: Fix bug"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("docs: Update documentation"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("style: Format code"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("refactor: Refactor code"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("perf: Improve performance"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("test: Add tests"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("build: Update build process"), "patch")
#         self.assertEqual(manager._parse_conventional_commit("ci: Update CI config"), "patch")

#         # Test with breaking changes
#         self.assertEqual(manager._parse_conventional_commit("feat: Add new feature with BREAKING CHANGE"), "major")
#         self.assertEqual(manager._parse_conventional_commit("fix: Fix bug\n\nBREAKING CHANGE: API change"), "major")

#         # Test with scopes
#         self.assertEqual(manager._parse_conventional_commit("feat(ui): Add button"), "minor")
#         self.assertEqual(manager._parse_conventional_commit("feat[ui]: Add button"), "minor")

#         # Test non-conventional commits
#         self.assertEqual(manager._parse_conventional_commit("Add a new feature"), "patch")
#         self.assertEqual(manager._parse_conventional_commit(""), None)

#     def test_version_bump_logic(self):
#         """Test the version bumping logic."""
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, self.initial_commit)

#         # Test major bumps
#         self.assertEqual(manager._bump_version("1.2.3", "major"), "2.0.0")
#         self.assertEqual(manager._bump_version("0.1.0", "major"), "1.0.0")

#         # Test minor bumps
#         self.assertEqual(manager._bump_version("1.2.3", "minor"), "1.3.0")
#         self.assertEqual(manager._bump_version("1.0.0", "minor"), "1.1.0")

#         # Test patch bumps
#         self.assertEqual(manager._bump_version("1.2.3", "patch"), "1.2.4")
#         self.assertEqual(manager._bump_version("1.0.0", "patch"), "1.0.1")

#         # Test invalid bump type
#         self.assertEqual(manager._bump_version("1.2.3", "invalid"), "1.2.3")

#     def test_patch_version_bump(self):
#         """Test that a patch commit triggers a patch version bump."""
#         # Make a patch change to feluda
#         patch_commit = self._make_changes_and_commit("feluda", "fix: Fix a bug in feluda")

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, patch_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that feluda version was bumped
#         self.assertIn("feluda", updated_versions)
#         self.assertEqual(updated_versions["feluda"]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions["feluda"]["new_version"], "0.1.1")
#         self.assertEqual(updated_versions["feluda"]["bump_type"], "patch")

#         # Check that the version was actually updated in the file
#         self.assertEqual(self._get_current_version("feluda"), "0.1.1")

#         # Check that a tag was created
#         tags = self._run_git_command(["git", "tag", "-l"]).stdout.strip().split("\n")
#         self.assertIn("feluda-v0.1.1", tags)

#     def test_minor_version_bump(self):
#         """Test that a minor commit triggers a minor version bump."""
#         # Make a minor change to an operator
#         minor_commit = self._make_changes_and_commit("operators/operator1", "feat: Add new feature to operator1")

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, minor_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that operator1 version was bumped
#         self.assertIn(os.path.join("operators", "operator1"), updated_versions)
#         self.assertEqual(updated_versions[os.path.join("operators", "operator1")]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator1")]["new_version"], "0.2.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator1")]["bump_type"], "minor")

#         # Check that the version was actually updated in the file
#         self.assertEqual(self._get_current_version(os.path.join("operators", "operator1")), "0.2.0")

#         # Check that a tag was created
#         tags = self._run_git_command(["git", "tag", "-l"]).stdout.strip().split("\n")
#         self.assertIn("operator1-v0.2.0", tags)

#     def test_major_version_bump(self):
#         """Test that a breaking change triggers a major version bump."""
#         # Make a breaking change to an operator
#         major_commit = self._make_changes_and_commit(
#             "operators/operator2",
#             "feat: Add new feature\n\nBREAKING CHANGE: This changes the API"
#         )

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, major_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that operator2 version was bumped
#         self.assertIn(os.path.join("operators", "operator2"), updated_versions)
#         self.assertEqual(updated_versions[os.path.join("operators", "operator2")]["old_version"], "0.2.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator2")]["new_version"], "1.0.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator2")]["bump_type"], "major")

#         # Check that the version was actually updated in the file
#         self.assertEqual(self._get_current_version(os.path.join("operators", "operator2")), "1.0.0")

#         # Check that a tag was created
#         tags = self._run_git_command(["git", "tag", "-l"]).stdout.strip().split("\n")
#         self.assertIn("operator2-v1.0.0", tags)

#     def test_multiple_packages_update(self):
#         """Test updating multiple packages with different changes."""
#         # Make changes to multiple packages
#         commit1 = self._make_changes_and_commit("feluda", "fix: Fix a bug in feluda")
#         commit2 = self._make_changes_and_commit("operators/operator1", "feat: Add new feature to operator1")
#         final_commit = self._make_changes_and_commit(
#             "operators/operator2",
#             "feat: Add new feature\n\nBREAKING CHANGE: This changes the API"
#         )

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, final_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that all packages were updated correctly
#         self.assertEqual(len(updated_versions), 3)

#         self.assertIn("feluda", updated_versions)
#         self.assertEqual(updated_versions["feluda"]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions["feluda"]["new_version"], "0.1.1")
#         self.assertEqual(updated_versions["feluda"]["bump_type"], "patch")

#         self.assertIn(os.path.join("operators", "operator1"), updated_versions)
#         self.assertEqual(updated_versions[os.path.join("operators", "operator1")]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator1")]["new_version"], "0.2.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator1")]["bump_type"], "minor")

#         self.assertIn(os.path.join("operators", "operator2"), updated_versions)
#         self.assertEqual(updated_versions[os.path.join("operators", "operator2")]["old_version"], "0.2.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator2")]["new_version"], "1.0.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "operator2")]["bump_type"], "major")

#         # Check that all versions were updated in files
#         self.assertEqual(self._get_current_version("feluda"), "0.1.1")
#         self.assertEqual(self._get_current_version(os.path.join("operators", "operator1")), "0.2.0")
#         self.assertEqual(self._get_current_version(os.path.join("operators", "operator2")), "1.0.0")

#         # Check that all tags were created
#         tags = self._run_git_command(["git", "tag", "-l"]).stdout.strip().split("\n")
#         self.assertIn("feluda-v0.1.1", tags)
#         self.assertIn("operator1-v0.2.0", tags)
#         self.assertIn("operator2-v1.0.0", tags)

#     def test_no_changes_no_bump(self):
#         """Test that packages with no changes don't get version bumps."""
#         # Make changes to only one package
#         commit = self._make_changes_and_commit("feluda", "fix: Fix a bug in feluda")

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that only feluda was updated
#         self.assertEqual(len(updated_versions), 1)
#         self.assertIn("feluda", updated_versions)
#         self.assertNotIn(os.path.join("operators", "operator1"), updated_versions)
#         self.assertNotIn(os.path.join("operators", "operator2"), updated_versions)

#         # Check that only feluda's version was updated in files
#         self.assertEqual(self._get_current_version("feluda"), "0.1.1")
#         self.assertEqual(self._get_current_version(os.path.join("operators", "operator1")), "0.1.0")
#         self.assertEqual(self._get_current_version(os.path.join("operators", "operator2")), "0.2.0")

#     def test_highest_bump_type_wins(self):
#         """Test that the highest bump type wins when multiple commit types affect a package."""
#         # Make multiple changes to a package with different bump types
#         commit1 = self._make_changes_and_commit("feluda", "fix: Fix a bug in feluda")
#         commit2 = self._make_changes_and_commit("feluda", "feat: Add new feature to feluda")
#         final_commit = self._make_changes_and_commit("feluda", "docs: Update documentation")

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, final_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that feluda was updated with a minor bump (from feat)
#         self.assertIn("feluda", updated_versions)
#         self.assertEqual(updated_versions["feluda"]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions["feluda"]["new_version"], "0.2.0")
#         self.assertEqual(updated_versions["feluda"]["bump_type"], "minor")

#     def test_tag_exists_skips_update(self):
#         """Test that packages with existing tags for the calculated version don't get updated."""
#         # Make changes to feluda
#         commit = self._make_changes_and_commit("feluda", "fix: Fix a bug in feluda")

#         # Manually create a tag for the next version to simulate a previous release
#         self._run_git_command(["git", "tag", "feluda-v0.1.1"])

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that feluda was not updated since the tag exists
#         self.assertEqual(len(updated_versions), 0)
#         self.assertNotIn("feluda", updated_versions)

#         # Check that feluda's version was not updated in file
#         self.assertEqual(self._get_current_version("feluda"), "0.1.0")

#     def test_missing_pyproject_file(self):
#         """Test handling of packages with missing pyproject.toml files."""
#         # Create a new package directory without a pyproject.toml
#         invalid_pkg_dir = os.path.join(self.operators_dir, "invalid_pkg")
#         os.makedirs(invalid_pkg_dir, exist_ok=True)

#         # Add a file to make it count as a change
#         with open(os.path.join(invalid_pkg_dir, "__init__.py"), "w") as f:
#             f.write('"""Invalid package."""\n')

#         # Commit the new package
#         self._run_git_command(["git", "add", invalid_pkg_dir])
#         final_commit = self._run_git_command(["git", "commit", "-m", "Add invalid package"])
#         final_commit_hash = self._get_current_commit()

#         # Initialize version manager - it should not raise an exception
#         # but log an error for the invalid package
#         with patch('builtins.print') as mock_print:
#             manager = PackageVersionManager(self.temp_dir, self.initial_commit, final_commit_hash)

#             # Verify that an error was logged
#             for call in mock_print.call_args_list:
#                 if "Error discovering package" in call[0][0] and "invalid_pkg" in call[0][0]:
#                     break
#             else:
#                 self.fail("No error was logged for the invalid package")

#             # The invalid package should not be in the discovered packages
#             self.assertNotIn(os.path.join("operators", "invalid_pkg"), manager.packages)

#     def test_invalid_version_format(self):
#         """Test handling of packages with invalid version formats."""
#         # Create a package with an invalid version format
#         invalid_version_dir = os.path.join(self.operators_dir, "invalid_version")
#         os.makedirs(invalid_version_dir, exist_ok=True)

#         # Create pyproject.toml with invalid version
#         pyproject_data = tomlkit.document()
#         project = tomlkit.table()
#         project["name"] = "invalid_version"
#         project["version"] = "invalid-version"
#         pyproject_data["project"] = project

#         tool = tomlkit.table()
#         semantic_release = tomlkit.table()
#         branches = tomlkit.table()
#         main = tomlkit.table()
#         main["tag_format"] = "invalid_version-v{version}"
#         branches["main"] = main
#         semantic_release["branches"] = branches
#         tool["semantic_release"] = semantic_release
#         pyproject_data["tool"] = tool

#         pyproject_path = os.path.join(invalid_version_dir, "pyproject.toml")
#         with open(pyproject_path, "w") as f:
#             f.write(tomlkit.dumps(pyproject_data))

#         # Commit the invalid package
#         self._run_git_command(["git", "add", invalid_version_dir])
#         final_commit = self._run_git_command(["git", "commit", "-m", "Add package with invalid version"])
#         final_commit_hash = self._get_current_commit()

#         # Make a change to trigger a version bump
#         change_file = os.path.join(invalid_version_dir, "change.py")
#         with open(change_file, "w") as f:
#             f.write("# Change in invalid_version\n")

#         self._run_git_command(["git", "add", change_file])
#         final_commit = self._run_git_command(["git", "commit", "-m", "fix: Change in invalid_version"])
#         final_commit_hash = self._get_current_commit()

#         # Initialize version manager
#         with patch('builtins.print') as mock_print:
#             manager = PackageVersionManager(self.temp_dir, self.initial_commit, final_commit_hash)

#             # Update versions - it should not raise an exception but log an error
#             updated_versions = manager.update_package_versions()

#             # Verify that errors were logged
#             found_error = False
#             for call in mock_print.call_args_list:
#                 args = call[0][0]
#                 if "Failed to update version" in args and "invalid_version" in args:
#                     found_error = True
#                     break

#             self.assertTrue(found_error, "No error was logged for the invalid version package")

#             # Check that the invalid package was not updated
#             self.assertNotIn(os.path.join("operators", "invalid_version"), updated_versions)

#     def test_adding_new_package(self):
#         """Test version management when adding a new package."""
#         # Add a new package
#         new_pkg_dir = os.path.join(self.operators_dir, "new_package")
#         self._create_package_files(os.path.join("operators", "new_package"), "0.1.0")

#         # Commit the new package
#         self._run_git_command(["git", "add", new_pkg_dir])
#         new_pkg_commit = self._run_git_command(["git", "commit", "-m", "feat: Add new package"])
#         new_pkg_commit_hash = self._get_current_commit()

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, new_pkg_commit_hash)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # New package should not get a version bump just for being added
#         # as it doesn't have any changes between the commits except its creation
#         self.assertNotIn(os.path.join("operators", "new_package"), updated_versions)

#         # Now make a change to the new package
#         change_commit = self._make_changes_and_commit(
#             os.path.join("operators", "new_package"),
#             "fix: Fix a bug in new_package"
#         )

#         # Initialize version manager again
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, change_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Now the new package should get a version bump
#         self.assertIn(os.path.join("operators", "new_package"), updated_versions)
#         self.assertEqual(updated_versions[os.path.join("operators", "new_package")]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions[os.path.join("operators", "new_package")]["new_version"], "0.1.1")

#     def test_non_conventional_commit(self):
#         """Test handling of non-conventional commit messages."""
#         # Make a change with a non-conventional commit message
#         non_conv_commit = self._make_changes_and_commit("feluda", "Added a new feature without conventional format")

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, self.initial_commit, non_conv_commit)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Non-conventional commits should be treated as patch updates
#         self.assertIn("feluda", updated_versions)
#         self.assertEqual(updated_versions["feluda"]["old_version"], "0.1.0")
#         self.assertEqual(updated_versions["feluda"]["new_version"], "0.1.1")
#         self.assertEqual(updated_versions["feluda"]["bump_type"], "patch")

#     def test_real_world_package_structure(self):
#         """Test with the exact structure of a real-world package."""
#         # Create a package with the exact structure provided in the example
#         real_pkg_dir = os.path.join(self.operators_dir, "real_package")
#         os.makedirs(real_pkg_dir, exist_ok=True)

#         # Create pyproject.toml with exact structure from real project
#         pyproject_content = """
# [project]
# name = "feluda-image-vec-rep-resnet"
# version = "0.1.3"
# requires-python = ">=3.10"
# dependencies = [
#     "torch>=2.5.1",
#     "torchvision>=0.20.1",
#     "numpy>=2.2.1",
#     "pillow>=11.1.0",
# ]

# [build-system]
# requires = ["hatchling"]
# build-backend = "hatchling.build"

# [tool.semantic_release]
# version_variable = ["pyproject.toml:project.version"]

# [tool.semantic_release.branches.main]
# match = "main"
# prerelease = false
# tag_format = "{name}-{version}"

# [tool.hatch.build.targets.wheel]
# packages = ["."]
# """
#         pyproject_path = os.path.join(real_pkg_dir, "pyproject.toml")
#         with open(pyproject_path, "w") as f:
#             f.write(pyproject_content)

#         # Create a Python file
#         with open(os.path.join(real_pkg_dir, "__init__.py"), "w") as f:
#             f.write('"""Real-world package structure."""\n\n__version__ = "0.1.3"\n')

#         # Commit the package
#         self._run_git_command(["git", "add", real_pkg_dir])
#         initial_pkg_commit = self._run_git_command(["git", "commit", "-m", "Add real-world package structure"])
#         initial_pkg_hash = self._get_current_commit()

#         # Make a series of changes with different commit types
#         patch_commit = self._make_changes_and_commit(
#             os.path.join("operators", "real_package"),
#             "fix: Fix a bug in the feature extraction"
#         )

#         minor_commit = self._make_changes_and_commit(
#             os.path.join("operators", "real_package"),
#             "feat: Add new image processing capability"
#         )

#         docs_commit = self._make_changes_and_commit(
#             os.path.join("operators", "real_package"),
#             "docs: Update API documentation"
#         )

#         final_commit_hash = self._get_current_commit()

#         # Initialize version manager
#         manager = PackageVersionManager(self.temp_dir, initial_pkg_hash, final_commit_hash)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that the package was updated with a minor bump (due to feat commit)
#         real_pkg_path = os.path.join("operators", "real_package")
#         self.assertIn(real_pkg_path, updated_versions)
#         self.assertEqual(updated_versions[real_pkg_path]["old_version"], "0.1.3")
#         self.assertEqual(updated_versions[real_pkg_path]["new_version"], "0.2.0")
#         self.assertEqual(updated_versions[real_pkg_path]["bump_type"], "minor")

#         # Check version in the pyproject.toml file
#         with open(pyproject_path, "r") as f:
#             updated_data = tomlkit.parse(f.read())
#             self.assertEqual(updated_data["project"]["version"], "0.2.0")
#             self.assertEqual(updated_data["project"]["name"], "feluda-image-vec-rep-resnet")
#             self.assertEqual(updated_data["project"]["requires-python"], ">=3.10")

#         # Check that a tag was created with the exact format
#         tags = self._run_git_command(["git", "tag", "-l"]).stdout.strip().split("\n")
#         self.assertIn("feluda-image-vec-rep-resnet-0.2.0", tags)

#         # Test a major version bump
#         major_commit = self._make_changes_and_commit(
#             os.path.join("operators", "real_package"),
#             "feat: Add new transformer architecture\n\nBREAKING CHANGE: This completely changes the API"
#         )
#         major_commit_hash = self._get_current_commit()

#         # Initialize version manager for the major change
#         manager = PackageVersionManager(self.temp_dir, final_commit_hash, major_commit_hash)

#         # Update versions
#         updated_versions = manager.update_package_versions()

#         # Check that the package was updated with a major bump
#         self.assertIn(real_pkg_path, updated_versions)
#         self.assertEqual(updated_versions[real_pkg_path]["old_version"], "0.2.0")
#         self.assertEqual(updated_versions[real_pkg_path]["new_version"], "1.0.0")
#         self.assertEqual(updated_versions[real_pkg_path]["bump_type"], "major")

#         # Check that a tag was created with the exact format
#         tags = self._run_git_command(["git", "tag", "-l"]).stdout.strip().split("\n")
#         self.assertIn("feluda-image-vec-rep-resnet-1.0.0", tags)
