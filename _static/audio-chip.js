// Play/pause controller for `.audio-chip` buttons (from _ext/icm_audio.py).
// Each chip lazily creates its Audio on first click; starting one pauses any
// other. The `is-playing` class swaps the icon and the `.acr-fill` ring
// tracks position. A chip inside an `.audio-track` row (the {showcase}
// card, _ext/icm_showcase.py) also drives that row's seek bar and time
// readout. Chips created after page load (by live-cells.js) are wired
// through window.icmWireAudioChip so all chips share the same
// exclusive-playback state.
(function () {
  "use strict";

  var playing = null; // the Audio currently playing, if any

  // m:ss, or –:–– until the duration is known.
  function fmtTime(s) {
    if (!isFinite(s)) return "–:––";
    s = Math.floor(s);
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  function wire(chip) {
    if (chip.dataset.acWired) return; // idempotent: safe to call twice
    var src = chip.getAttribute("data-audio-src");
    if (!src) return;
    chip.dataset.acWired = "1";
    var fill = chip.querySelector(".acr-fill"); // progress ring arc
    // Seek bar and time readout, present only in an .audio-track row.
    var track = chip.closest(".audio-track");
    var seek = track ? track.querySelector(".audio-seek") : null;
    var cur = track ? track.querySelector(".audio-time-cur") : null;
    var dur = track ? track.querySelector(".audio-time-dur") : null;
    var audio = null;
    var raf = null;
    var scrubbing = false; // pointer is down on the seek bar

    function setRing(offset) {
      if (fill) fill.style.strokeDashoffset = String(offset);
    }
    // Ring, seek bar, and time readout for a played percentage.
    function setPos(pct, t) {
      setRing(100 - pct);
      if (seek && !scrubbing) {
        seek.value = String(Math.round(pct * 10)); // max="1000"
        seek.style.setProperty("--p", pct + "%");
      }
      if (cur) cur.textContent = fmtTime(t);
    }
    // Drive the ring per animation frame — `timeupdate` only fires ~4×/s
    // and looks chunky.
    function loop() {
      if (audio.duration)
        setPos((audio.currentTime / audio.duration) * 100, audio.currentTime);
      raf = requestAnimationFrame(loop);
    }
    function stopLoop() {
      if (raf) cancelAnimationFrame(raf);
      raf = null;
    }

    function ensureAudio() {
      if (audio) return audio;
      audio = new Audio(src);
      audio.preload = "metadata";
      audio.addEventListener("play", function () {
        if (playing && playing !== audio) playing.pause();
        playing = audio;
        chip.classList.add("is-playing");
        stopLoop();
        loop();
      });
      audio.addEventListener("pause", function () {
        chip.classList.remove("is-playing");
        if (playing === audio) playing = null;
        stopLoop();
      });
      audio.addEventListener("ended", function () {
        chip.classList.remove("is-playing");
        if (playing === audio) playing = null;
        stopLoop();
        setPos(0, 0); // reset the ring (and seek bar) to empty
      });
      // Fires with the metadata, and again if a VBR estimate is refined.
      if (dur)
        audio.addEventListener("durationchange", function () {
          dur.textContent = fmtTime(audio.duration);
        });
      return audio;
    }

    chip.addEventListener("click", function () {
      var a = ensureAudio();
      if (a.paused) a.play();
      else a.pause();
    });

    if (seek) {
      ensureAudio(); // up front, so the duration shows before the first play
      // While the pointer is down the loop leaves the bar alone; the
      // release can land outside the bar, hence window.
      seek.addEventListener("pointerdown", function () {
        scrubbing = true;
      });
      window.addEventListener("pointerup", function () {
        scrubbing = false;
      });
      window.addEventListener("pointercancel", function () {
        scrubbing = false;
      });
      seek.addEventListener("input", function () {
        var a = ensureAudio();
        var pct = Number(seek.value) / 10;
        seek.style.setProperty("--p", pct + "%");
        if (!a.duration) return; // no metadata yet; the loop catches up on play
        var target = (pct / 100) * a.duration;
        a.currentTime = target;
        setRing(100 - pct);
        // Show the target: currentTime can read back stale until the seek lands.
        if (cur) cur.textContent = fmtTime(target);
      });
    }
  }

  window.icmWireAudioChip = wire;

  function init() {
    document.querySelectorAll(".audio-chip").forEach(wire);
  }

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();
