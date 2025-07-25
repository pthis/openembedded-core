SUMMARY = "initramfs-framework module for live booting"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"
RDEPENDS:${PN} = "initramfs-framework-base udev-extraconf"

inherit allarch

FILESEXTRAPATHS:prepend := "${THISDIR}/initramfs-framework:"
SRC_URI = "file://setup-live"

S = "${UNPACKDIR}"

do_install() {
    install -d ${D}/init.d
    install -m 0755 ${S}/setup-live ${D}/init.d/80-setup-live
}

FILES:${PN} = "/init.d/80-setup-live"
