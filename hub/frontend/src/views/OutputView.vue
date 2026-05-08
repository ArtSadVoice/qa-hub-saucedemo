<script setup lang="ts">
import FilesView from './FilesView.vue'

const downloadHref = (file: string, pid: string) => `/api/output/download?p=${pid}&f=${encodeURIComponent(file)}`
</script>

<template>
  <FilesView kind="output" title="Output (Reports)" icon="📤" :downloadHref="downloadHref" />
</template>
