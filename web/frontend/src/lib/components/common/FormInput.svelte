<script lang="ts">
  import Icon from "@iconify/svelte";

  // FormInput component props
  export let type: "text" | "number" | "email" | "password" = "text";
  export let value: string | number = "";
  export let placeholder: string = "";
  export let label: string = "";
  export let required: boolean = false;
  export let disabled: boolean = false;
  export let error: string = "";
  export let helperText: string = "";
  export let icon: string | null = null;
  export let min: number | undefined = undefined;
  export let max: number | undefined = undefined;
  export let step: number | undefined = undefined;
  export let id: string = "";

  // Generate unique ID if not provided
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;

  // Event handlers
  export let onInput: ((value: string | number) => void) | undefined =
    undefined;
  export let onBlur: ((event: FocusEvent) => void) | undefined = undefined;
  export let onFocus: ((event: FocusEvent) => void) | undefined = undefined;

  // Handle input events
  const handleInput = (event: Event) => {
    const target = event.target as HTMLInputElement;
    const newValue = type === "number" ? Number(target.value) : target.value;
    value = newValue;
    onInput?.(newValue);
  };

  const handleBlur = (event: FocusEvent) => {
    onBlur?.(event);
  };

  const handleFocus = (event: FocusEvent) => {
    onFocus?.(event);
  };

  // Reactive classes
  $: hasError = error && error.length > 0;
  $: baseClasses =
    "w-full px-3 py-2 text-sm border rounded-lg transition-colors focus:outline-none focus:ring-2";
  $: stateClasses = hasError
    ? "border-red-300 focus:ring-red-500 focus:border-red-500"
    : "border-gray-300 focus:ring-blue-500 focus:border-blue-500";
  $: disabledClasses = disabled ? "bg-gray-100 cursor-not-allowed" : "bg-white";
  $: iconClasses = icon ? "pl-10" : "";
  $: inputClasses = `${baseClasses} ${stateClasses} ${disabledClasses} ${iconClasses}`;
</script>

<div class="w-full">
  <!-- Label -->
  {#if label}
    <label for={inputId} class="block text-sm font-medium text-gray-700 mb-2">
      {label}
      {#if required}
        <span class="text-red-500 ml-1">*</span>
      {/if}
    </label>
  {/if}

  <!-- Input container -->
  <div class="relative">
    <!-- Icon -->
    {#if icon}
      <div
        class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none"
      >
        <Icon {icon} class="w-4 h-4 text-gray-400" />
      </div>
    {/if}

    <!-- Input field -->
    <input
      {type}
      id={inputId}
      bind:value
      {placeholder}
      {required}
      {disabled}
      {min}
      {max}
      {step}
      class={inputClasses}
      on:input={handleInput}
      on:blur={handleBlur}
      on:focus={handleFocus}
    />
  </div>

  <!-- Helper text and error -->
  {#if hasError || helperText}
    <div class="mt-1 min-h-[1.25rem]">
      {#if hasError}
        <p class="text-sm text-red-600 flex items-center gap-1">
          <Icon icon="material-symbols:error" class="w-4 h-4" />
          {error}
        </p>
      {:else if helperText}
        <p class="text-sm text-gray-500">
          {helperText}
        </p>
      {/if}
    </div>
  {/if}
</div>

