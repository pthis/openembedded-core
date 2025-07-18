SUMMARY = "A clock combined with a game of pong"
LICENSE = "GPL-2.0-or-later"
DEPENDS = "virtual/libx11 xdmcp xau"

inherit features_check pkgconfig
# depends on virtual/libx11
REQUIRED_DISTRO_FEATURES = "x11"

SRC_URI = "file://pong-clock-no-flicker.c"

LIC_FILES_CHKSUM = "file://pong-clock-no-flicker.c;beginline=1;endline=23;md5=dd248d50f73f746d1ee78586b0b2ebd3"

S = "${UNPACKDIR}"

do_compile () {
	${CC} ${CFLAGS} ${LDFLAGS} -o pong-clock pong-clock-no-flicker.c `pkg-config --cflags --libs x11 xau xdmcp`
}

do_install () {
	install -d ${D}${bindir}
	install -m 0755 pong-clock ${D}${bindir}
}
