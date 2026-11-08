<script setup lang="ts">
import { Head, Link } from '@inertiajs/vue3'

defineProps<{ user: { name: string; email: string } }>()
</script>

<template>
    <Head title="Dashboard" />
    <main class="mx-auto mt-16 max-w-3xl px-4">
        <div class="flex items-center justify-between gap-4">
            <h1 class="text-2xl font-semibold tracking-tight">Dashboard</h1>
            <Link href="/logout" method="post" as="button" class="text-sm font-medium text-emerald-700 hover:underline">Log out</Link>
        </div>
        <p class="mt-4">Welcome back, {{ user.name }}. This is your dashboard.</p>
        <p class="mt-1 text-sm text-stone-600">Signed in as {{ user.email }}</p>
    </main>
</template>
