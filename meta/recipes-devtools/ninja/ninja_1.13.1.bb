SUMMARY = "Ninja is a small build system with a focus on speed."
HOMEPAGE = "https://ninja-build.org/"
DESCRIPTION = "Ninja is a small build system with a focus on speed. \
It differs from other build systems in two major respects: \
it is designed to have its input files generated by a higher-level build system, \
and it is designed to run builds as fast as possible."

LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://COPYING;md5=a81586a64ad4e476c791cda7e2f2c52e"

DEPENDS = "re2c-native ninja-native"

SRCREV = "79feac0f3e3bc9da9effc586cd5fea41e7550051"

SRC_URI = "git://github.com/ninja-build/ninja.git;branch=release;protocol=https;tag=v${PV}"
UPSTREAM_CHECK_GITTAGREGEX = "v(?P<pver>.*)"

do_configure[noexec] = "1"

do_compile:class-native() {
	python3 ./configure.py --bootstrap
}

do_compile() {
	python3 ./configure.py
	ninja
}

do_install() {
	install -D -m 0755  ${S}/ninja ${D}${bindir}/ninja
}

BBCLASSEXTEND = "native nativesdk"

CVE_STATUS[CVE-2021-4336] = "cpe-incorrect: This is a different Ninja"
