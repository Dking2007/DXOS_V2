<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Desktiny contributors -->
<!-- The entrance: a framed title card on a deep blue ground that always fits one screen, one way in
     through the organisation's SSO. Everything moves gently and stays still for reduced motion. -->
<script setup lang="ts">
import { ChevronRight, TriangleAlert } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { appearance, brand } from '../ui/appearance'

const route = useRoute()
// The sector pack in force may name the organisation, change the titles and the ground.
const entry = computed(() => appearance.value?.login ?? {})
const style = computed(() => entry.value.style ?? 'framed')
const ground = computed(() =>
  style.value === 'image' && entry.value.background_url
    ? { backgroundImage: `linear-gradient(160deg, rgba(8, 22, 52, 0.78), rgba(8, 22, 52, 0.55)), url("${entry.value.background_url}")` }
    : undefined,
)
const busy = ref(false)
function login() {
  busy.value = true
  window.location.assign('/workspace/v1/auth/login')
}
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
  <main class="entry" :class="`entry-${style}`" :style="ground">
    <div v-if="style === 'framed'" class="entry-light" aria-hidden="true" />
    <div v-if="style === 'framed'" class="entry-specks" aria-hidden="true">
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
      <svg
        v-for="corner in ['tl', 'tr', 'bl', 'br']"
        :key="corner"
        :class="['entry-corner', corner]"
        viewBox="0 0 120 120"
      >
        <path pathLength="1" d="M2 40 V2 H40" />
        <path pathLength="1" d="M14 70 V14 H70" />
        <path pathLength="1" d="M28 90 C28 52 52 28 90 28" />
        <rect x="8" y="8" width="12" height="12" transform="rotate(45 14 14)" />
        <circle cx="28" cy="90" r="2.2" />
        <circle cx="90" cy="28" r="2.2" />
      </svg>
    </div>

    <section class="entry-card" aria-labelledby="entry-title">
      <p class="entry-org rise" style="--d: 0.15s">
        <span>{{ brand.org ? brand.org.toLocaleUpperCase('vi') : 'VĂN PHÒNG ĐIỆN TỬ' }}</span>
      </p>

      <div class="entry-emblem rise" style="--d: 0.3s" aria-hidden="true">
        <span class="entry-emblem-ring"
          ><span class="entry-emblem-core" :class="{ 'has-logo': !!brand.logo }"
            ><img v-if="brand.logo" :src="brand.logo" alt="" /><template v-else>{{
              brand.name.charAt(0)
            }}</template></span
          ></span
        >
      </div>

      <p class="entry-kicker rise" style="--d: 0.5s"><span>{{ brand.name.toLocaleUpperCase('vi') }}</span></p>
      <h1 id="entry-title" class="entry-title rise" style="--d: 0.65s">
        <template v-if="entry.title">{{ entry.title }}</template
        ><template v-else>Hệ thống văn phòng điện tử<br />hồ sơ, tài liệu và phê duyệt</template>
      </h1>
      <div class="entry-divider rise" style="--d: 0.85s" aria-hidden="true">
        <i />
      </div>
      <p class="entry-code rise" style="--d: 0.95s">
        {{ entry.subtitle || 'E-OFFICE · KHÔNG GIAN NỘI BỘ' }}
      </p>

      <div class="entry-actions rise" style="--d: 1.15s">
        <p v-if="route.query.connection" class="entry-warning" role="alert">
          <TriangleAlert :size="16" />Chưa kết nối được máy chủ. Thử đăng nhập
          lại sau ít phút.
        </p>
        <button
          class="entry-button"
          type="button"
          :disabled="busy"
          @click="login"
        >
          <span>{{
            busy ? 'Đang chuyển tới trang đăng nhập…' : 'Đăng nhập bằng SSO'
          }}</span>
          <ChevronRight :size="20" aria-hidden="true" />
        </button>
        <p class="entry-note">
          Đăng nhập bằng tài khoản của tổ chức. {{ brand.name }} không lưu mật khẩu của
          bạn.
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
.entry.entry-image {
  background-size: cover;
  background-position: center;
}
.entry-emblem-core.has-logo {
  overflow: hidden;
  padding: 18%;
  background: #fff;
  border-radius: 50%;
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
    rgba(160, 190, 240, 0.17),
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
  background: #d8e6ff;
  box-shadow: 0 0 8px 2px rgba(170, 200, 255, 0.55);
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

/* The frame draws itself in, then the corners. */
.entry-frame {
  position: absolute;
  inset: 22px;
  border: 1px solid var(--line);
  outline: 1px solid rgba(205, 220, 245, 0.16);
  outline-offset: -10px;
  pointer-events: none;
  animation: frame-in 1.2s cubic-bezier(0.2, 0.7, 0.2, 1) both;
}
@keyframes frame-in {
  from {
    opacity: 0;
    inset: 46px;
  }
}
.entry-corner {
  position: absolute;
  width: 110px;
  height: 110px;
  fill: none;
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
@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}
.entry-corner rect {
  fill: none;
  stroke-width: 1.6;
  animation: diamond 4s 1.6s ease-in-out infinite;
}
@keyframes diamond {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}
.entry-corner circle {
  fill: rgba(225, 235, 250, 0.85);
  stroke: none;
}
.entry-corner.tl {
  top: 6px;
  left: 6px;
}
.entry-corner.tr {
  top: 6px;
  right: 6px;
  transform: scaleX(-1);
}
.entry-corner.bl {
  bottom: 6px;
  left: 6px;
  transform: scaleY(-1);
}
.entry-corner.br {
  bottom: 6px;
  right: 6px;
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
    rgba(120, 160, 230, 0.18),
    rgba(120, 160, 230, 0) 70%
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
    #d9e4f7,
    #8fa9d6,
    #f3f7ff,
    #7f9ccd,
    #d9e4f7
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
  background: radial-gradient(circle at 35% 30%, #2b5bb0, #12306a 70%);
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
  line-height: 1.22;
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
  box-shadow: 0 0 10px rgba(200, 220, 255, 0.8);
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
  gap: calc(var(--u) * 1.4);
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
  background: linear-gradient(
    180deg,
    rgba(70, 84, 112, 0.85),
    rgba(28, 36, 56, 0.92)
  );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 12px 30px rgba(2, 8, 24, 0.45);
  color: #f4f7fc;
  font: inherit;
  font-size: clamp(16px, calc(var(--u) * 1.9), 19px);
  font-weight: 600;
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
.entry-button svg {
  transition: transform 0.2s;
}
.entry-button:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(240, 246, 255, 0.9);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    0 0 24px rgba(140, 180, 255, 0.35),
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
  margin: 0;
  color: rgba(205, 218, 238, 0.72);
  font-family: 'Source Sans 3', sans-serif;
  font-size: clamp(13px, calc(var(--u) * 1.5), 15px);
}
.entry-warning {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 8px 14px;
  border: 1px solid rgba(251, 191, 36, 0.45);
  border-radius: 10px;
  background: rgba(120, 80, 10, 0.35);
  color: #fde7b0;
  font-family: 'Source Sans 3', sans-serif;
  font-size: 14px;
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
  .entry-corner {
    width: 64px;
    height: 64px;
  }
  .entry-org {
    letter-spacing: 0.3em;
    gap: 12px;
  }
  .entry-title {
    font-size: 21px;
    line-height: 1.35;
  }
  .entry-code {
    letter-spacing: 0.24em;
  }
  .entry-button {
    padding: 0 26px 0 30px;
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
  .entry-light,
  .entry-specks i,
  .entry-frame,
  .entry-corner rect,
  .entry-emblem::after,
  .entry-emblem-ring::before,
  .entry-button::before,
  .rise,
  .entry-title {
    animation: none;
  }
  .entry-corner path {
    animation: none;
    stroke-dashoffset: 0;
  }
  .entry-specks {
    display: none;
  }
  .entry-button,
  .entry-button svg {
    transition: none;
  }
}
</style>
