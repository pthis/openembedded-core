SUMMARY = "Linux man-pages"
DESCRIPTION = "The Linux man-pages project documents the Linux kernel and C library interfaces that are employed by user programs"
SECTION = "console/utils"
HOMEPAGE = "http://www.kernel.org/pub/linux/docs/man-pages"
LICENSE = "GPL-2.0-or-later & GPL-2.0-only & GPL-1.0-or-later & BSD-2-Clause & BSD-3-Clause & BSD-4-Clause-UC & MIT"

LIC_FILES_CHKSUM = "file://README;md5=72cff06b7954222c24d38bc2c41b234e \
                    file://LICENSES/BSD-2-Clause.txt;md5=9e16594a228301089d759b4f178db91f \
                    file://LICENSES/BSD-3-Clause.txt;md5=407426fcc1a243b7b2eff6e35c56aca9 \
                    file://LICENSES/BSD-4-Clause-UC.txt;md5=1da3cf8ad50cd8d5d1de3cfc53196d01 \
                    file://LICENSES/GPL-1.0-or-later.txt;md5=e5b7c80002ef72ab868b43ce47b65125 \
                    file://LICENSES/GPL-2.0-only.txt;md5=3d26203303a722dedc6bf909d95ba815 \
                    file://LICENSES/GPL-2.0-or-later.txt;md5=3d26203303a722dedc6bf909d95ba815 \
                    file://LICENSES/Linux-man-pages-1-para.txt;md5=97ab07585ce6700273bc66461bf46bf2 \
                    file://LICENSES/Linux-man-pages-copyleft-2-para.txt;md5=1cafc230857da5e43f3d509c425d3c64 \
                    file://LICENSES/Linux-man-pages-copyleft.txt;md5=173b960c686ff2d26f043ddaeb63f6ce \
                    file://LICENSES/Linux-man-pages-copyleft-var.txt;md5=d33708712c5918521f47f23b0c4e0d20 \
                    file://LICENSES/MIT.txt;md5=7dda4e90ded66ab88b86f76169f28663 \
                    "
SRC_URI = "${KERNELORG_MIRROR}/linux/docs/${BPN}/${BP}.tar.gz \
           "

SRC_URI[sha256sum] = "a298963d8baf37fa5ecd2b07c803e1f29ab0476add405a7e263e5c63baf43588"

inherit manpages lib_package

MAN_PKG = "${PN}"

PACKAGECONFIG ??= ""
PACKAGECONFIG[manpages] = ""

do_configure[noexec] = "1"
do_compile[noexec] = "1"

EXTRA_OEMAKE += "-R"
do_install() {
        oe_runmake install prefix=${prefix} DESTDIR=${D}
        rm -rf ${D}${mandir}/man3/crypt.3
        rm -rf ${D}${mandir}/man3/crypt_r.3
        rm -rf ${D}${mandir}/man3/getspnam.3
        rm -rf ${D}${mandir}/man5/passwd.5
}

RDEPENDS:${PN}-bin += " \
    bash \
"

# Only deliveres man-pages so FILES:${PN} gets everything
FILES:${PN}-doc = ""
FILES:${PN} = "${mandir}/*"
