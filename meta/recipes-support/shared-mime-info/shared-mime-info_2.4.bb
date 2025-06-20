SUMMARY = "Shared MIME type database and specification"
DESCRIPTION = "The shared-mime-info package contains the core database of common types."
HOMEPAGE = "http://freedesktop.org/wiki/Software/shared-mime-info"
SECTION = "base"

LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=b234ee4d69f5fce4486a80fdaf4a4263"

DEPENDS = "libxml2 glib-2.0 shared-mime-info-native xmlto-native"

SRC_URI = "git://gitlab.freedesktop.org/xdg/shared-mime-info.git;protocol=https;branch=master \
           file://0001-Fix-build-with-libxml2-2.12.0-and-clang-17.patch \
           file://0002-Handle-build-with-older-versions-of-GCC.patch"
SRCREV = "9a6d6b8e963935f145f3a1ef446552de6996dada"

inherit meson pkgconfig gettext python3native mime

EXTRA_OEMESON = "-Dupdate-mimedb=true"

FILES:${PN} += "${datadir}/mime"
FILES:${PN}-dev += "${datadir}/pkgconfig/shared-mime-info.pc ${datadir}/gettext/its"

# freedesktop.org.xml is only required when updating the mime database,
# package it separately
PACKAGES =+ "shared-mime-info-data"
FILES:shared-mime-info-data = "${datadir}/mime/packages/freedesktop.org.xml"
RDEPENDS:shared-mime-info-data = "shared-mime-info"

BBCLASSEXTEND = "native nativesdk"
