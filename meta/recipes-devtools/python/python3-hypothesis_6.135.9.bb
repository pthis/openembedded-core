SUMMARY = "A library for property-based testing"
HOMEPAGE = "https://github.com/HypothesisWorks/hypothesis/tree/master/hypothesis-python"
LICENSE = "MPL-2.0"
LIC_FILES_CHKSUM = "file://LICENSE.txt;md5=4ee62c16ebd0f4f99d906f36b7de8c3c"

PYPI_PACKAGE = "hypothesis"
PTEST_PYTEST_DIR ?= "examples"

inherit pypi python_setuptools_build_meta ptest-python-pytest

SRC_URI += " \
    file://test_binary_search.py \
    file://test_rle.py \
    "

SRC_URI[sha256sum] = "a80a256268b8af3d34d62be30f6bf4a7d099b2b762621cc5f3f1de65e7b98543"

RDEPENDS:${PN} += " \
    python3-attrs \
    python3-compression \
    python3-core \
    python3-json \
    python3-pytest \
    python3-sortedcontainers \
    python3-statistics \
    python3-unittest \
    python3-zoneinfo \
    "

do_install_ptest:append() {
    install -d ${D}${PTEST_PATH}/${PTEST_PYTEST_DIR}
    install -m 0755 ${UNPACKDIR}/test_binary_search.py ${D}${PTEST_PATH}/${PTEST_PYTEST_DIR}/
    install -m 0755 ${UNPACKDIR}/test_rle.py ${D}${PTEST_PATH}/${PTEST_PYTEST_DIR}/
}

BBCLASSEXTEND = "native nativesdk"
