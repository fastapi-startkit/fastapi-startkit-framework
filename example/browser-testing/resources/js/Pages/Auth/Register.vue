<script setup lang="ts">
import { Head, Link, useForm } from '@inertiajs/vue3'

const form = useForm({ name: '', email: '', password: '' })
</script>

<template>
    <Head title="Create your account" />
    <main class="mx-auto mt-16 max-w-sm px-4">
        <h1 class="text-2xl font-semibold tracking-tight">Create your account</h1>
        <form class="mt-8 space-y-5" @submit.prevent="form.post('/register')">
            <div>
                <label for="name" class="block text-sm font-medium">Name</label>
                <input id="name" v-model="form.name" name="name" autocomplete="name" class="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" />
                <p v-if="form.errors.name" class="mt-1 text-sm text-red-700">{{ form.errors.name }}</p>
            </div>
            <div>
                <label for="email" class="block text-sm font-medium">Email address</label>
                <input id="email" v-model="form.email" name="email" type="email" autocomplete="email" class="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" />
                <p v-if="form.errors.email" class="mt-1 text-sm text-red-700">{{ form.errors.email }}</p>
            </div>
            <div>
                <label for="password" class="block text-sm font-medium">Password</label>
                <input id="password" v-model="form.password" name="password" type="password" autocomplete="new-password" class="mt-1 w-full rounded-md border border-stone-300 px-3 py-2" />
                <p v-if="form.errors.password" class="mt-1 text-sm text-red-700">{{ form.errors.password }}</p>
            </div>
            <button type="submit" :disabled="form.processing" class="w-full rounded-md bg-emerald-700 px-4 py-2 font-medium text-white hover:bg-emerald-800">
                Create account
            </button>
        </form>
        <p class="mt-6 text-center text-sm">
            Already have an account?
            <Link href="/login" class="font-medium text-emerald-700 hover:underline">Sign In</Link>
        </p>
    </main>
</template>
