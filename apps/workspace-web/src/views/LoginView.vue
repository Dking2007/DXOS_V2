<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- The entrance: a framed title card that always fits one screen, one way in through the organisation's SSO.
     The frame (double rule, silver corners, a light travelling round the edge), the beam and the specks are the
     stock "framed" style; a sector pack may choose "flat" or "image" instead. Everything stays still for reduced
     motion or when the pack turns effects off. -->
<script setup lang="ts">
import { ChevronRight, Loader2, TriangleAlert } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { STOCK_LOGO, appearance, brand } from '../ui/appearance'

const route = useRoute()
// The sector pack in force may name the organisation, change the titles and the ground.
const entry = computed(() => appearance.value?.login ?? {})
const style = computed(() => entry.value.style ?? 'framed')
const effects = computed(() => entry.value.effects !== false)
// The pack's ground colours, as CSS variables the styles below read; the photo is tinted with them.
const ground = computed(() => {
  const from = entry.value.ground || null
  const to = entry.value.ground_to || from
  const result: Record<string, string> = {}
  if (from && to) {
    result['--ground-from'] = from
    result['--ground-to'] = to
  }
  if (style.value === 'image' && entry.value.background_url) {
    const tint = from && to
      ? `color-mix(in srgb, ${from} 80%, transparent), color-mix(in srgb, ${to} 58%, transparent)`
      : 'rgba(8, 22, 52, 0.78), rgba(8, 22, 52, 0.55)'
    result.backgroundImage = `linear-gradient(160deg, ${tint}), url("${entry.value.background_url}")`
  }
  return result
})
const busy = ref(false)
let stuck = 0
function login() {
  if (busy.value) return
  busy.value = true
  window.location.assign('/workspace/v1/auth/login')
  // If the sign-in page never loads (offline, blocked), give the button back instead of spinning forever.
  stuck = window.setTimeout(() => (busy.value = false), 15_000)
}
// Coming back with the browser's Back button restores this page from the cache with the button
// still saying "Đang chuyển…"; make it usable again.
function onPageShow(event: PageTransitionEvent) {
  if (event.persisted) {
    window.clearTimeout(stuck)
    busy.value = false
  }
}
onMounted(() => window.addEventListener('pageshow', onPageShow))
onBeforeUnmount(() => {
  window.removeEventListener('pageshow', onPageShow)
  window.clearTimeout(stuck)
})
// Specks of light drifting up; fixed positions so the page looks the same on every visit.
const SPECKS = [
  [6, 14, 0],
  [14, 22, 3.5],
  [22, 18, 7],
  [31, 26, 1.8],
  [38, 16, 5.2],
  [47, 24, 9],
  [55, 20, 2.6],
  [63, 28, 6.4],
  [71, 17, 4.1],
  [79, 23, 8.2],
  [87, 19, 0.9],
  [94, 25, 5.8],
].map(([left, duration, delay]) => ({
  left: `${left}%`,
  duration: `${duration}s`,
  delay: `-${delay}s`,
}))
</script>

<template>
  <main
    class="entry"
    :class="[`entry-${style}`, { 'has-ground': !!entry.ground, 'entry-still': !effects }]"
    :style="ground"
  >
    <div v-if="style === 'framed' && effects" class="entry-light" aria-hidden="true" />
    <div v-if="style === 'framed' && effects" class="entry-specks" aria-hidden="true">
      <i
        v-for="(speck, index) in SPECKS"
        :key="index"
        :style="{
          left: speck.left,
          animationDuration: speck.duration,
          animationDelay: speck.delay,
        }"
      />
    </div>
    <div v-if="style === 'framed'" class="entry-frame" aria-hidden="true">
      <span class="entry-comet" />
      <i v-for="side in ['t', 'r', 'b', 'l']" :key="side" :class="['entry-mark', side]" />
      <svg
        v-for="corner in ['tl', 'tr', 'bl', 'br']"
        :key="corner"
        :class="['entry-corner', corner]"
        viewBox="0 0 120 120"
      >
        <defs>
          <linearGradient :id="`entry-silver-${corner}`" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#ffffff" />
            <stop offset="0.45" stop-color="#c9d7ef" />
            <stop offset="1" stop-color="#c9d7ef" stop-opacity="0" />
          </linearGradient>
        </defs>
        <!-- A bright cap over the frame's own corner, an inner bracket, a flourish between them. -->
        <path class="cap" pathLength="1" :stroke="`url(#entry-silver-${corner})`" d="M0 62 V0 H62" />
        <path pathLength="1" d="M11 40 V11 H40" />
        <path class="flourish" pathLength="1" d="M22 84 C22 48 48 22 84 22" />
        <path class="tick" pathLength="1" d="M11 50 V56 M50 11 H56" />
        <circle cx="22" cy="84" r="1.8" />
        <circle cx="84" cy="22" r="1.8" />
        <circle cx="11" cy="11" r="1.6" />
        <rect class="gem" x="-5.5" y="-5.5" width="11" height="11" transform="rotate(45)" />
      </svg>
    </div>

    <section class="entry-card" aria-labelledby="entry-title">
      <p class="entry-org rise" style="--d: 0.15s">
        <span>{{ brand.org ? brand.org.toLocaleUpperCase('vi') : 'VĂN PHÒNG ĐIỆN TỬ' }}</span>
      </p>

      <div class="entry-emblem rise" style="--d: 0.3s" aria-hidden="true">
        <span class="entry-emblem-ring"
          ><span class="entry-emblem-core has-logo" :class="{ stock: !brand.logo }"
            ><img :src="brand.logo || STOCK_LOGO" alt="" /></span
          ></span
        >
      </div>

      <p class="entry-kicker rise" style="--d: 0.5s"><span>{{ brand.name.toLocaleUpperCase('vi') }}</span></p>
      <h1 id="entry-title" class="entry-title rise" style="--d: 0.65s">
        <template v-if="entry.title">{{ entry.title }}</template
        ><template v-else
          ><span class="entry-phrase">Hệ thống</span>{{ ' ' }}<span class="entry-phrase">văn phòng điện tử</span
          ><br /><span class="entry-phrase">hồ sơ, tài liệu</span>{{ ' ' }}<span class="entry-phrase"
            >và phê duyệt</span
          ></template
        >
      </h1>
      <div class="entry-divider rise" style="--d: 0.85s" aria-hidden="true">
        <i />
      </div>
      <p class="entry-code rise" style="--d: 0.95s">
        {{ entry.subtitle || 'E-OFFICE · KHÔNG GIAN NỘI BỘ' }}
      </p>

      <div class="entry-actions rise" style="--d: 1.15s">
        <p v-if="route.query.connection" class="entry-warning" role="alert">
          <TriangleAlert :size="16" aria-hidden="true" /><span
            >Chưa kết nối được máy chủ. Thử đăng nhập lại sau ít phút.</span
          >
        </p>
        <p v-else-if="route.query.login" class="entry-warning" role="alert">
          <TriangleAlert :size="16" aria-hidden="true" /><span>{{
            route.query.login === 'expired'
              ? 'Phiên đăng nhập đã hết hạn do để trang đăng nhập quá lâu. Bấm đăng nhập lại để tiếp tục.'
              : 'Phiên đăng nhập không hợp lệ (có thể do mở nhiều tab đăng nhập). Bấm đăng nhập lại.'
          }}</span>
        </p>
        <button
          class="entry-button"
          type="button"
          :disabled="busy"
          :aria-busy="busy"
          @click="login"
        >
          <span>{{
            busy ? 'Đang chuyển tới trang đăng nhập…' : entry.button_label || 'Đăng nhập bằng SSO'
          }}</span>
          <Loader2 v-if="busy" :size="20" class="entry-spin" aria-hidden="true" />
          <ChevronRight v-else :size="20" aria-hidden="true" />
        </button>
        <p class="entry-note">
          <template v-if="entry.note">{{ entry.note }}</template
          ><template v-else
            >Đăng nhập bằng tài khoản của tổ chức. {{ brand.name }} không lưu mật khẩu của bạn.</template
          >
        </p>
      </div>
    </section>
  </main>
</template>

<style scoped>
/* Pack login styles: "flat" keeps the card on the pack's main colour, "image" puts it on a photo. */
.entry.entry-flat {
  background: linear-gradient(160deg, var(--teal-strong, #16304f), var(--teal, #1e3a5f));
}
/* A pack's ground colours carry through the light, the silver and the button, so nothing stays stock blue. */
.entry.has-ground {
  --glow: color-mix(in srgb, var(--ground-from) 28%, #fff);
  --metal-1: color-mix(in srgb, var(--ground-from) 8%, #f2f2f2);
  --metal-2: color-mix(in srgb, var(--ground-from) 30%, #a6a6a6);
  --metal-3: #ffffff;
  --metal-4: color-mix(in srgb, var(--ground-from) 38%, #8f8f8f);
  --core-1: color-mix(in srgb, var(--ground-from) 70%, #fff);
  --core-2: var(--ground-from);
  --button-top: color-mix(in srgb, var(--ground-from) 78%, #fff);
  --button-bottom: color-mix(in srgb, var(--ground-from) 70%, #000);
}
/* A pack's own ground colours, for "framed" and "flat" (the photo is tinted in the script). */
.entry.has-ground:not(.entry-image) {
  background:
    radial-gradient(90% 70% at 50% 110%, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 70%),
    linear-gradient(160deg, var(--ground-from) 0%, var(--ground-to) 100%);
}
.entry.entry-image {
  background-size: cover;
  background-position: center;
}
/* Effects switched off by the pack: everything stands still, as for reduced motion. */
.entry-still .entry-frame,
.entry-still .entry-corner rect,
.entry-still .entry-emblem::after,
.entry-still .entry-emblem-ring::before,
.entry-still .entry-button::before,
.entry-still .entry-title {
  animation: none;
}
.entry-still .entry-corner path {
  animation: none;
  stroke-dashoffset: 0;
}
.entry-still .entry-comet {
  display: none;
}
.entry-emblem-core.has-logo {
  overflow: hidden;
  padding: 16%;
  background: radial-gradient(circle at 35% 30%, #fff, var(--metal-1));
  border-radius: 50%;
}
.entry-emblem-core.stock {
  /* Desktiny's own mark is a full tile: it sits larger in the silver ring than a pack's flat logo. */
  padding: 12%;
}
.entry-emblem-core.has-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.entry {
  --ink: #e8eef8;
  --soft: #b9c6db;
  --line: rgba(205, 220, 245, 0.42);
  /* Light, metal and button tones; a pack's ground colours retint them (has-ground below). */
  --glow: rgb(170 200 255);
  --metal-1: #d9e4f7;
  --metal-2: #8fa9d6;
  --metal-3: #f3f7ff;
  --metal-4: #7f9ccd;
  --core-1: #2b5bb0;
  --core-2: #12306a;
  --button-top: rgba(70, 84, 112, 0.85);
  --button-bottom: rgba(28, 36, 56, 0.92);
  /* One scale for everything, from the smaller of the screen's height and width, so it always fits. */
  --u: min(1vh, 0.62vw);
  position: relative;
  height: 100dvh;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: max(40px, calc(var(--u) * 7)) 24px;
  overflow: hidden;
  color: var(--ink);
  background:
    radial-gradient(120% 90% at 50% 0%, #1f4384 0%, rgba(31, 67, 132, 0) 60%),
    radial-gradient(90% 70% at 50% 110%, #050c1e 0%, rgba(5, 12, 30, 0) 70%),
    linear-gradient(160deg, #183670 0%, #0f2554 48%, #081634 100%);
  font-family: 'Be Vietnam Pro', 'Source Sans 3', sans-serif;
}
@supports (height: 100dvh) {
  .entry {
    min-height: 0;
  }
}
/* Fine diagonal grain over the whole ground. */
.entry::before {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    115deg,
    rgba(255, 255, 255, 0.025) 0 1px,
    transparent 1px 14px
  );
  pointer-events: none;
}
/* A soft beam of light drifting slowly across. */
.entry-light {
  position: absolute;
  top: -20%;
  left: 8%;
  width: 22%;
  height: 140%;
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--glow) 17%, transparent),
    transparent
  );
  transform: rotate(18deg);
  filter: blur(8px);
  pointer-events: none;
  animation: beam 16s ease-in-out infinite alternate;
}
@keyframes beam {
  from {
    transform: translateX(-12vw) rotate(18deg);
    opacity: 0.6;
  }
  to {
    transform: translateX(46vw) rotate(18deg);
    opacity: 1;
  }
}
.entry-specks {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.entry-specks i {
  position: absolute;
  bottom: -10px;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--glow) 60%, #fff);
  box-shadow: 0 0 8px 2px color-mix(in srgb, var(--glow) 55%, transparent);
  opacity: 0;
  animation: speck linear infinite;
}
.entry-specks i:nth-child(3n) {
  width: 2px;
  height: 2px;
}
@keyframes speck {
  0% {
    transform: translate(0, 0);
    opacity: 0;
  }
  15% {
    opacity: 0.8;
  }
  85% {
    opacity: 0.5;
  }
  100% {
    transform: translate(30px, -105vh);
    opacity: 0;
  }
}

/* The frame: a double rule that draws itself in, brighter towards the corners, with a light travelling round. */
@property --entry-turn {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}
.entry-frame {
  --frame-ground: var(--ground-from, #102a5e);
  --rule: rgba(205, 220, 245, 0.22);
  --rule-bright: rgba(230, 238, 252, 0.75);
  position: absolute;
  inset: 22px;
  pointer-events: none;
  /* A faint glow inside the frame, as if the card were lit from within. */
  box-shadow: inset 0 0 140px color-mix(in srgb, var(--glow) 8%, transparent);
  animation: frame-in 1.2s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
.entry-frame::before,
.entry-frame::after {
  content: '';
  position: absolute;
  pointer-events: none;
}
/* Outer rule: strongest at the corners, quieter along the middle of each side. */
.entry-frame::before {
  inset: 0;
  background:
    linear-gradient(90deg, var(--rule-bright), var(--rule) 28%, var(--rule) 72%, var(--rule-bright)) top / 100% 1px
      no-repeat,
    linear-gradient(90deg, var(--rule-bright), var(--rule) 28%, var(--rule) 72%, var(--rule-bright)) bottom / 100%
      1px no-repeat,
    linear-gradient(180deg, var(--rule-bright), var(--rule) 28%, var(--rule) 72%, var(--rule-bright)) left / 1px
      100% no-repeat,
    linear-gradient(180deg, var(--rule-bright), var(--rule) 28%, var(--rule) 72%, var(--rule-bright)) right / 1px
      100% no-repeat;
}
/* Inner rule, set in a little and broken at the corners where the brackets sit. */
.entry-frame::after {
  --gap: 96px;
  inset: 11px;
  border: 1px solid rgba(205, 220, 245, 0.16);
  -webkit-mask:
    linear-gradient(#000 0 0) center / calc(100% - var(--gap)) 100% no-repeat,
    linear-gradient(#000 0 0) center / 100% calc(100% - var(--gap)) no-repeat;
  mask:
    linear-gradient(#000 0 0) center / calc(100% - var(--gap)) 100% no-repeat,
    linear-gradient(#000 0 0) center / 100% calc(100% - var(--gap)) no-repeat;
}
@keyframes frame-in {
  from {
    opacity: 0;
    inset: 46px;
  }
}
/* A soft light running round the outer rule, once about every half minute. */
.entry-comet {
  position: absolute;
  inset: -1px;
  padding: 2px;
  background: conic-gradient(
    from var(--entry-turn),
    transparent 0deg 318deg,
    color-mix(in srgb, var(--glow) 25%, transparent) 338deg,
    rgba(240, 246, 255, 0.95) 354deg,
    transparent 360deg
  );
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask:
    linear-gradient(#000 0 0) content-box exclude,
    linear-gradient(#000 0 0);
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--glow) 80%, transparent));
  opacity: 0.8;
  animation: comet 28s 1.8s linear infinite;
}
@keyframes comet {
  to {
    --entry-turn: 360deg;
  }
}
/* A small diamond in the middle of each side, sitting on the rule. */
.entry-mark {
  position: absolute;
  width: 9px;
  height: 9px;
  border: 1px solid rgba(230, 238, 252, 0.85);
  background: var(--frame-ground);
  transform: rotate(45deg);
  box-shadow: 0 0 10px color-mix(in srgb, var(--glow) 45%, transparent);
}
.entry-mark::before {
  content: '';
  position: absolute;
  inset: 2px;
  background: rgba(230, 238, 252, 0.85);
}
.entry-mark.t,
.entry-mark.b {
  left: calc(50% - 5px);
}
.entry-mark.t {
  top: -5px;
}
.entry-mark.b {
  bottom: -5px;
}
.entry-mark.l,
.entry-mark.r {
  top: calc(50% - 5px);
}
.entry-mark.l {
  left: -5px;
}
.entry-mark.r {
  right: -5px;
}
/* Silver corners: a bright cap over the frame's corner, an inner bracket, a flourish and a jewel. */
.entry-corner {
  position: absolute;
  width: 120px;
  height: 120px;
  overflow: visible;
  fill: none;
  stroke: rgba(225, 235, 250, 0.62);
  stroke-width: 1.1;
  stroke-linecap: round;
}
.entry-corner .cap {
  stroke-width: 2.2;
  filter: drop-shadow(0 0 3px color-mix(in srgb, var(--glow) 55%, transparent));
}
.entry-corner .flourish {
  stroke: rgba(225, 235, 250, 0.4);
}
.entry-corner .tick {
  stroke: rgba(225, 235, 250, 0.75);
  stroke-width: 1.4;
}
.entry-corner path {
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: draw 1.4s 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
.entry-corner path:nth-of-type(2) {
  animation-delay: 0.7s;
}
.entry-corner path:nth-of-type(3) {
  animation-delay: 0.9s;
}
.entry-corner path:nth-of-type(4) {
  animation-delay: 1.1s;
}
@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}
.entry-corner circle {
  fill: rgba(225, 235, 250, 0.85);
  stroke: none;
}
.entry-corner .gem {
  fill: var(--frame-ground);
  stroke: #eef4ff;
  stroke-width: 1.3;
  filter: drop-shadow(0 0 5px color-mix(in srgb, var(--glow) 90%, transparent));
  animation: diamond 4s 1.6s ease-in-out infinite;
}
@keyframes diamond {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}
.entry-corner.tl {
  top: 0;
  left: 0;
}
.entry-corner.tr {
  top: 0;
  right: 0;
  transform: scaleX(-1);
}
.entry-corner.bl {
  bottom: 0;
  left: 0;
  transform: scaleY(-1);
}
.entry-corner.br {
  bottom: 0;
  right: 0;
  transform: scale(-1);
}

.entry-card {
  position: relative;
  z-index: 1;
  width: min(100%, 1100px);
  max-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
/* Each part rises into place, one after another. */
.rise {
  animation: rise 0.9s var(--d, 0s) cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(18px);
    filter: blur(4px);
  }
}
/* Spaced capitals between two hairlines. */
.entry-org,
.entry-kicker {
  display: flex;
  align-items: center;
  gap: 22px;
  margin: 0;
  color: var(--soft);
  font-weight: 600;
  letter-spacing: 0.42em;
  text-indent: 0.42em;
}
.entry-org::before,
.entry-org::after,
.entry-kicker::before,
.entry-kicker::after {
  content: '';
  width: clamp(32px, calc(var(--u) * 7), 80px);
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--line));
}
.entry-org::after,
.entry-kicker::after {
  background: linear-gradient(90deg, var(--line), transparent);
}
.entry-org {
  font-size: clamp(11px, calc(var(--u) * 1.5), 15px);
}
.entry-emblem {
  position: relative;
  display: grid;
  place-items: center;
  width: clamp(110px, calc(var(--u) * 21), 200px);
  aspect-ratio: 1;
  margin: calc(var(--u) * 4) 0 calc(var(--u) * 2.6);
  border-radius: 50%;
  background: radial-gradient(
    circle,
    color-mix(in srgb, var(--glow) 18%, transparent),
    color-mix(in srgb, var(--glow) 0%, transparent) 70%
  );
  box-shadow:
    0 0 0 1px rgba(205, 220, 245, 0.16),
    0 0 0 14px rgba(205, 220, 245, 0.04);
}
/* A slow halo breathing around the emblem. */
.entry-emblem::after {
  content: '';
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  border: 1px solid rgba(190, 210, 245, 0.35);
  animation: halo 3.6s 1.4s ease-out infinite;
  opacity: 0;
}
@keyframes halo {
  0% {
    transform: scale(0.92);
    opacity: 0.7;
  }
  100% {
    transform: scale(1.22);
    opacity: 0;
  }
}
.entry-emblem-ring {
  position: relative;
  display: grid;
  place-items: center;
  width: 74%;
  aspect-ratio: 1;
  border-radius: 50%;
  padding: 7px;
  overflow: hidden;
  box-shadow: 0 14px 40px rgba(2, 8, 24, 0.55);
}
/* The silver ring turns slowly, catching the light. */
.entry-emblem-ring::before {
  content: '';
  position: absolute;
  inset: -20%;
  background: conic-gradient(
    from 210deg,
    var(--metal-1),
    var(--metal-2),
    var(--metal-3),
    var(--metal-4),
    var(--metal-1)
  );
  animation: turn 9s linear infinite;
}
@keyframes turn {
  to {
    transform: rotate(360deg);
  }
}
.entry-emblem-core {
  position: relative;
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, var(--core-1), var(--core-2) 70%);
  color: #f4f8ff;
  font-size: clamp(42px, calc(var(--u) * 6.6), 66px);
  font-weight: 600;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
}
.entry-kicker {
  font-size: clamp(14px, calc(var(--u) * 2), 20px);
  color: #dfe8f7;
}
/* Silver lettering with a sheen passing over it now and then. */
.entry-title {
  margin: calc(var(--u) * 2.2) 0 0;
  font-size: clamp(21px, min(4.1vw, calc(var(--u) * 5.6)), 56px);
  line-height: 1.35;
  /* background-clip: text paints only inside the box; stacked marks (Ử, Ệ) need room. */
  padding-block: 0.18em 0.08em;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.01em;
  background:
    linear-gradient(
      105deg,
      transparent 0%,
      transparent 42%,
      rgba(255, 255, 255, 0.95) 50%,
      transparent 58%,
      transparent 100%
    ),
    linear-gradient(180deg, #ffffff 0%, #dbe3ef 55%, #a9b6ca 100%);
  background-size:
    250% 100%,
    100% 100%;
  background-repeat: no-repeat;
  background-position:
    150% 0,
    0 0;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  filter: drop-shadow(0 3px 8px rgba(0, 0, 0, 0.35));
  animation:
    rise 0.9s var(--d, 0s) cubic-bezier(0.2, 0.7, 0.2, 1) both,
    sheen 6s 2s ease-in-out infinite;
}
/* The stock title wraps between phrases, never inside one. */
.entry-phrase {
  white-space: nowrap;
}
@keyframes sheen {
  0%,
  55% {
    background-position:
      150% 0,
      0 0;
  }
  100% {
    background-position:
      -50% 0,
      0 0;
  }
}
.entry-divider {
  display: flex;
  align-items: center;
  gap: 14px;
  width: min(480px, 70%);
  margin: calc(var(--u) * 3) 0 calc(var(--u) * 2.2);
}
.entry-divider::before,
.entry-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--line));
}
.entry-divider::after {
  background: linear-gradient(90deg, var(--line), transparent);
}
.entry-divider i {
  width: 7px;
  height: 7px;
  background: #dfe8f7;
  transform: rotate(45deg);
  box-shadow: 0 0 10px color-mix(in srgb, var(--glow) 80%, transparent);
}
.entry-code {
  margin: 0;
  color: var(--soft);
  font-size: clamp(11px, calc(var(--u) * 1.6), 16px);
  font-weight: 600;
  letter-spacing: 0.36em;
  text-indent: 0.36em;
}
.entry-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: max(12px, calc(var(--u) * 1.6));
  max-width: 100%;
  margin-top: calc(var(--u) * 5.5);
}
.entry-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 16px;
  min-height: clamp(48px, calc(var(--u) * 6.4), 62px);
  padding: 0 34px 0 40px;
  overflow: hidden;
  border: 1px solid rgba(225, 235, 250, 0.55);
  border-radius: 999px;
  background: linear-gradient(180deg, var(--button-top), var(--button-bottom));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 12px 30px rgba(2, 8, 24, 0.45);
  max-width: 100%;
  color: #f4f7fc;
  font: inherit;
  font-size: clamp(16px, calc(var(--u) * 1.9), 19px);
  font-weight: 600;
  line-height: 1.3;
  text-align: center;
  cursor: pointer;
  transition:
    transform 0.2s,
    box-shadow 0.2s,
    border-color 0.2s;
}
/* A streak of light sweeps the button every few seconds. */
.entry-button::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -60%;
  width: 45%;
  background: linear-gradient(
    100deg,
    transparent,
    rgba(255, 255, 255, 0.28),
    transparent
  );
  transform: skewX(-20deg);
  animation: sweep 4.5s 2.4s ease-in-out infinite;
}
@keyframes sweep {
  0%,
  60% {
    left: -60%;
  }
  100% {
    left: 130%;
  }
}
.entry-button > * {
  position: relative;
}
.entry-button > span {
  min-width: 0;
  padding: 10px 0;
}
.entry-button svg {
  flex: none;
  transition: transform 0.2s;
}
.entry-spin {
  animation: entry-spin 1s linear infinite;
}
@keyframes entry-spin {
  to {
    transform: rotate(360deg);
  }
}
.entry-button:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(240, 246, 255, 0.9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    0 0 24px color-mix(in srgb, var(--glow) 35%, transparent),
    0 16px 36px rgba(2, 8, 24, 0.55);
}
.entry-button:hover:not(:disabled) svg {
  transform: translateX(4px);
}
.entry-button:active:not(:disabled) {
  transform: translateY(0);
}
.entry-button:focus-visible {
  outline: 2px solid #9cc0ff;
  outline-offset: 4px;
}
.entry-button:disabled {
  cursor: progress;
  opacity: 0.85;
}
.entry-note {
  max-width: 560px;
  margin: 0;
  line-height: 1.5;
  color: rgba(205, 218, 238, 0.78);
  font-family: 'Source Sans 3', sans-serif;
  font-size: clamp(13px, calc(var(--u) * 1.5), 15px);
}
.entry-warning > svg {
  flex: none;
}
.entry-warning {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
  margin: 0 0 4px;
  padding: 12px 16px;
  text-align: left;
  line-height: 1.45;
  border: 1px solid rgba(251, 191, 36, 0.45);
  border-radius: 10px;
  background: rgba(120, 80, 10, 0.35);
  color: #fde7b0;
  font-family: 'Source Sans 3', sans-serif;
  font-size: 0.875rem;
}

/* Tablets held upright: more height to fill, so the card grows with the width. */
@media (min-width: 721px) and (orientation: portrait) {
  .entry {
    --u: min(0.85vh, 1.05vw);
  }
}
@media (max-width: 720px) {
  .entry {
    --u: 0.82vh;
    padding: 48px 20px;
  }
  .entry-frame {
    inset: 10px;
  }
  .entry-frame::after {
    --gap: 60px;
    inset: 7px;
  }
  .entry-corner {
    width: 64px;
    height: 64px;
  }
  /* On a phone the side diamonds would crowd the text; keep top and bottom only. */
  .entry-mark.l,
  .entry-mark.r {
    display: none;
  }
  /* Tighter tracking so a phrase wraps by words instead of leaving one word alone. */
  .entry-org,
  .entry-kicker {
    letter-spacing: 0.18em;
    text-indent: 0.18em;
    gap: 12px;
  }
  .entry-title {
    font-size: 1.3125rem;
    line-height: 1.35;
    /* A pack's own title: even lines, so a narrow phone never leaves one word alone on a line. */
    text-wrap: balance;
  }
  /* The stock title already breaks between its phrases. */
  .entry-title:has(.entry-phrase) {
    text-wrap: wrap;
  }
  .entry-code {
    letter-spacing: 0.1em;
    text-indent: 0.1em;
    text-wrap: balance;
  }
  .entry-button {
    gap: 12px;
    padding: 0 22px 0 26px;
  }
  /* Long organisation names wrap instead of being cut by the frame. */
  .entry-org,
  .entry-kicker {
    max-width: 100%;
  }
  .entry-org span,
  .entry-kicker span {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  .entry-org::before,
  .entry-org::after,
  .entry-kicker::before,
  .entry-kicker::after {
    flex: none;
  }
}
/* A very short window (a phone on its side): let it scroll rather than squash. */
@media (max-height: 480px) {
  .entry {
    height: auto;
    min-height: 100dvh;
    overflow-y: auto;
  }
}
@media (prefers-reduced-motion: reduce) {
  :root:not([data-motion='full']) .entry-light,
  :root:not([data-motion='full']) .entry-specks i,
  :root:not([data-motion='full']) .entry-frame,
  :root:not([data-motion='full']) .entry-corner rect,
  :root:not([data-motion='full']) .entry-emblem::after,
  :root:not([data-motion='full']) .entry-emblem-ring::before,
  :root:not([data-motion='full']) .entry-button::before,
  :root:not([data-motion='full']) .rise,
  :root:not([data-motion='full']) .entry-title {
    animation: none;
  }
  :root:not([data-motion='full']) .entry-corner path {
    animation: none;
    stroke-dashoffset: 0;
  }
  :root:not([data-motion='full']) .entry-specks,
  :root:not([data-motion='full']) .entry-comet {
    display: none;
  }
  :root:not([data-motion='full']) .entry-button,
  :root:not([data-motion='full']) .entry-button svg {
    transition: none;
  }
}
</style>
