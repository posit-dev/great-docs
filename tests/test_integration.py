import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Path to the test-packages directory
TEST_PACKAGES_DIR = Path(__file__).parent.parent / "test-packages"


# Find the great-docs executable - prefer .venv if it exists
def _find_great_docs_executable():
    """Find the great-docs executable in .venv or system PATH."""
    venv_executable = Path(__file__).parent.parent / ".venv" / "bin" / "great-docs"
    if venv_executable.exists():
        return str(venv_executable)

    # Fallback to shutil.which
    system_executable = shutil.which("great-docs")
    if system_executable:
        return system_executable

    # Last resort: try running as module
    return None


GREAT_DOCS_CMD = _find_great_docs_executable()

# List of test packages - each should be a subdirectory in test-packages/
# Only test packages that actually exist
# Listed in order of preference: smaller/faster packages first
TEST_PACKAGES = [
    pkg
    for pkg in ["python-dateutil", "time-machine", "py-shiny", "ggsql-python"]
    if (TEST_PACKAGES_DIR / pkg).exists()
]


@pytest.mark.skipif(
    not TEST_PACKAGES,
    reason="No test packages found in test-packages/. Clone repos to enable integration tests.",
)
@pytest.mark.parametrize("package_name", TEST_PACKAGES)
def test_external_package_init_and_build(package_name):
    """Test that great-docs can initialize and build docs for an external package.

    This test:
    1. Runs 'great-docs init --force' on the package
    2. Runs 'great-docs build' on the package
    3. Checks that both commands complete successfully (exit code 0)
    4. Verifies that the build directory and key files are created

    Parameters
    ----------
    package_name
        Name of the package subdirectory in test-packages/
    """
    package_dir = TEST_PACKAGES_DIR / package_name
    assert package_dir.exists(), f"Package directory {package_dir} not found"

    # Clean up any existing great-docs artifacts
    config_file = package_dir / "great-docs.yml"
    build_dir = package_dir / "great-docs"

    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Step 1: Run great-docs init
    print(f"\n{'=' * 60}")
    print(f"Testing {package_name}: Running great-docs init")
    print(f"{'=' * 60}")

    if GREAT_DOCS_CMD:
        cmd = [GREAT_DOCS_CMD, "init", "--force"]
    else:
        # Fallback to module execution
        cmd = [sys.executable, "-m", "great_docs.cli", "init", "--force"]

    init_result = subprocess.run(
        cmd,
        cwd=package_dir,
        capture_output=True,
        text=True,
        timeout=60,
        input="",  # Provide empty input instead of DEVNULL
    )

    print(f"STDOUT:\n{init_result.stdout}")
    if init_result.stderr:
        print(f"STDERR:\n{init_result.stderr}")

    assert init_result.returncode == 0, (
        f"great-docs init failed for {package_name} with exit code {init_result.returncode}\n"
        f"STDOUT: {init_result.stdout}\n"
        f"STDERR: {init_result.stderr}"
    )

    # Verify config file was created
    assert config_file.exists(), f"Configuration file {config_file} was not created"

    # Step 2: Run great-docs build
    print(f"\n{'=' * 60}")
    print(f"Testing {package_name}: Running great-docs build")
    print(f"{'=' * 60}")

    if GREAT_DOCS_CMD:
        cmd = [GREAT_DOCS_CMD, "build"]
    else:
        cmd = [sys.executable, "-m", "great_docs.cli", "build"]

    build_result = subprocess.run(
        cmd,
        cwd=package_dir,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minutes timeout for build
        input="",  # Provide empty input instead of DEVNULL
    )

    print(f"STDOUT:\n{build_result.stdout}")
    if build_result.stderr:
        print(f"STDERR:\n{build_result.stderr}")

    assert build_result.returncode == 0, (
        f"great-docs build failed for {package_name} with exit code {build_result.returncode}\n"
        f"STDOUT: {build_result.stdout}\n"
        f"STDERR: {build_result.stderr}"
    )

    # Step 3: Verify build artifacts were created
    assert build_dir.exists(), f"Build directory {build_dir} was not created"

    site_dir = build_dir / "_site"
    assert site_dir.exists(), f"Site directory {site_dir} was not created"

    index_html = site_dir / "index.html"
    assert index_html.exists(), f"Index file {index_html} was not created"

    print(f"\n{'=' * 60}")
    print(f"✓ Successfully built docs for {package_name}")
    print(f"  - Config: {config_file}")
    print(f"  - Site: {site_dir}")
    print(f"  - To view: open {site_dir / 'index.html'}")
    print(f"{'=' * 60}")


@pytest.mark.skipif(not TEST_PACKAGES, reason="No test packages found in test-packages/.")
def test_test_packages_directory_exists():
    """Verify that the test-packages directory exists."""
    assert TEST_PACKAGES_DIR.exists(), (
        f"Test packages directory {TEST_PACKAGES_DIR} not found. "
        "Create it and clone test repositories."
    )


def test_can_list_test_packages():
    """List available test packages (for debugging)."""
    if not TEST_PACKAGES_DIR.exists():
        pytest.skip("test-packages directory does not exist")

    subdirs = [d for d in TEST_PACKAGES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    print(f"\nFound {len(subdirs)} subdirectories in test-packages/:")
    for subdir in subdirs:
        print(f"  - {subdir.name}")

    # Check for README
    readme = TEST_PACKAGES_DIR / "README.md"
    if readme.exists():
        print(f"\nREADME.md exists in test-packages/")

    print(f"\nTest packages that will be tested: {TEST_PACKAGES}")
