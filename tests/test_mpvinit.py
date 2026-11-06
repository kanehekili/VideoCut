"""mpv construction in the GL path must survive a GL stack that cannot serve us.

initPlayer (the wid path) has always had a try/except that falls back along the
vo chain gpu,xv,x11. initGLPlayer had none, so a machine without a usable GL
stack died with a traceback. It cannot use a vo chain: the render context only
receives frames from vo=libmpv, and any other vo would open a window of its own.
So the fallback switches the GL mode instead, with the two options tweakVirtual
would otherwise apply after construction.

Plain unittest, offscreen Qt, nothing installed beyond what VideoCut needs:

    cd /home/matze/git/VideoCut && python3 -m unittest discover -s tests
"""
import contextlib
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import MpvPlayer  # noqa: E402


@contextlib.contextmanager
def gpu(nvidia=False, virtual=False):
    """the box the suite runs on must not decide the outcome of a test"""
    with mock.patch.object(MpvPlayer.GPUTools, 'hasNvidiaDriver', return_value=nvidia), \
         mock.patch.object(MpvPlayer.GPUTools, 'isVirtualGpu', return_value=virtual):
        yield


def noNvidia():
    return gpu()


def withNvidia():
    return gpu(nvidia=True)


class MpvInitFallbackTest(unittest.TestCase):

    def setUp(self):
        self.player = MpvPlayer.MpvPlayer()
        # _hookEvents parses the real mpv version string; a MagicMock is not one
        patcher = mock.patch.object(MpvPlayer.MpvPlayer, 'mpvVersion', return_value='0.41.0')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_normalStartNeedsNoFallback(self):
        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV') as MPV:
            self.player.initGLPlayer()
            args = MPV.call_args.kwargs
        self.assertEqual(MPV.call_count, 1)
        self.assertEqual(args.get('vo'), 'libmpv')
        self.assertNotIn('gpu-dumb-mode', args, 'software rendering only on retry')

    def test_failureRetriesWithSoftwareRendering(self):
        made = []

        def fake(**kw):
            made.append(kw)
            if len(made) == 1:
                raise RuntimeError('no GL here')
            return mock.MagicMock()

        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV', side_effect=fake):
            self.assertIsNotNone(self.player.initGLPlayer())
        self.assertEqual(len(made), 2, 'exactly one retry')
        self.assertNotIn('gpu-dumb-mode', made[0])
        self.assertEqual(made[1].get('gpu-dumb-mode'), 'yes')
        self.assertEqual(made[1].get('vd-lavc-dr'), 'no')

    def test_voIsNeverChangedByTheFallback(self):
        """the wid path may chain gpu,xv,x11 - the render context may not"""
        made = []

        def fake(**kw):
            made.append(kw)
            if len(made) == 1:
                raise RuntimeError('no GL here')
            return mock.MagicMock()

        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV', side_effect=fake):
            self.player.initGLPlayer()
        for attempt in made:
            self.assertEqual(attempt.get('vo'), 'libmpv')

    def test_failureInSoftwareModeIsNotSwallowed(self):
        with noNvidia(), mock.patch.object(MpvPlayer, 'MPV', side_effect=RuntimeError('hopeless')) as MPV:
            with self.assertRaises(RuntimeError):
                self.player.initGLPlayer()
        self.assertEqual(MPV.call_count, 2, 'one retry, then give up honestly')

    def test_nvidiaStillGetsNvdec(self):
        with withNvidia(), mock.patch.object(MpvPlayer, 'MPV') as MPV:
            self.player.initGLPlayer()
            args = MPV.call_args.kwargs
        self.assertEqual(args.get('hwdec'), 'nvdec_copy')

    def test_interopIsNeverLeftToMpv(self):
        """vo=libmpv reads interop "auto" as "all" and dlopens libcuda.so.1 at
        render context creation, whatever hwdec says - so it is always explicit"""
        for kw in ({}, {'nvidia': True}, {'virtual': True}):
            with self.subTest(**kw), gpu(**kw), mock.patch.object(MpvPlayer, 'MPV') as MPV:
                self.player.initGLPlayer()
                self.assertEqual(MPV.call_args.kwargs.get('gpu-hwdec-interop'), 'no')


class WidVoChainTest(unittest.TestCase):
    """The wid path picks its vo chain from what the GPU detection found. On an
    emulated adapter the gpu VO must not even be offered: it probes egl, then drm
    - which wants DRM master, is refused and aborts the process rather than
    raising - so the try/except below could never catch it."""

    def built(self, **kw):
        player = MpvPlayer.MpvPlayer()
        container = mock.Mock(**{'winId.return_value': 42})
        with gpu(**kw), mock.patch.object(MpvPlayer.MpvPlayer, 'mpvVersion', return_value='0.41.0'), \
             mock.patch.object(MpvPlayer, 'MPV') as MPV:
            player.initPlayer(container)
            return MPV.call_args.kwargs

    def test_emulatedGpuNeverGetsTheGpuVo(self):
        args = self.built(virtual=True)
        self.assertEqual(args.get('vo'), 'xv,x11')
        self.assertEqual(args.get('hwdec'), 'no')
        self.assertEqual(args.get('gpu-dumb-mode'), 'yes')
        self.assertEqual(args.get('gpu-hwdec-interop'), 'no')

    def test_realGpuKeepsTheGpuVo(self):
        self.assertEqual(self.built().get('vo'), 'gpu,xv,x11')

    def test_nvidiaLeadsWithGpuNext(self):
        self.assertEqual(self.built(nvidia=True).get('vo'), 'gpu-next,gpu,xv,x11')

    def test_virtualFlagReachesTheWidPath(self):
        """-v means software rendering on both widgets, not just the GL one"""
        player = MpvPlayer.MpvPlayer()
        container = mock.Mock(**{'winId.return_value': 42})
        with gpu(), mock.patch.object(MpvPlayer.MpvPlayer, 'mpvVersion', return_value='0.41.0'), \
             mock.patch.object(MpvPlayer, 'MPV') as MPV:
            player.initPlayer(container, True)
            args = MPV.call_args.kwargs
        self.assertEqual(args.get('vo'), 'xv,x11')
        self.assertEqual(args.get('vd-lavc-dr'), 'no')


if __name__ == '__main__':
    unittest.main()
