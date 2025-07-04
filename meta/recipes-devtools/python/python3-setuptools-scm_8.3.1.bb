SUMMARY = "the blessed package to manage your versions by scm tags"
HOMEPAGE = "https://pypi.org/project/setuptools-scm/"
DESCRIPTION = "setuptools_scm handles managing your Python package \
versions in SCM metadata instead of declaring them as the version \
argument or in a SCM managed file."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=838c366f69b72c5df05c96dff79b35f2"

SRC_URI[sha256sum] = "3d555e92b75dacd037d32bafdf94f97af51ea29ae8c7b234cf94b7a5bd242a63"

PYPI_PACKAGE = "setuptools_scm"
UPSTREAM_CHECK_PYPI_PACKAGE = "${PYPI_PACKAGE}"

inherit pypi python_setuptools_build_meta

DEPENDS += "python3-packaging-native python3-typing-extensions-native"

RDEPENDS:${PN} = "\
    python3-packaging \
    python3-pip \
    python3-pyparsing \
    python3-setuptools \
    python3-typing-extensions \
"

RDEPENDS:${PN}:append:class-target = " \
    python3-debugger \
    python3-json \
"

BBCLASSEXTEND = "native nativesdk"
