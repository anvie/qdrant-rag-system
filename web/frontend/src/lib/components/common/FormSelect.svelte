<script lang="ts" context="module">
  export interface SelectOption {
    value: string | number;
    label: string;
    disabled?: boolean;
    description?: string;
  }
</script>

<script lang="ts">
  import Icon from '@iconify/svelte';

  // FormSelect component props
  export let value: string | number = '';
  export let options: SelectOption[] = [];
  export let placeholder: string = 'Select an option';
  export let label: string = '';
  export let required: boolean = false;
  export let disabled: boolean = false;
  export let error: string = '';
  export let helperText: string = '';
  export let icon: string | null = null;
  export let id: string = '';

  // Generate unique ID if not provided
  const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`;

  // Event handlers
  export let onChange: ((value: string | number) => void) | undefined = undefined;
  export let onBlur: ((event: FocusEvent) => void) | undefined = undefined;
  export let onFocus: ((event: FocusEvent) => void) | undefined = undefined;

  // Handle change events
  const handleChange = (event: Event) => {
    const target = event.target as HTMLSelectElement;
    const selectedOption = options.find(opt => opt.value.toString() === target.value);
    const newValue = selectedOption?.value || '';
    value = newValue;
    onChange?.(newValue);
  };

  const handleBlur = (event: FocusEvent) => {
    onBlur?.(event);
  };

  const handleFocus = (event: FocusEvent) => {
    onFocus?.(event);
  };

  // Reactive classes
  $: hasError = error && error.length > 0;
  $: baseClasses = 'w-full px-3 py-2 text-sm border rounded-lg transition-colors focus:outline-none focus:ring-2 appearance-none bg-no-repeat bg-right';
  $: stateClasses = hasError 
    ? 'border-red-300 focus:ring-red-500 focus:border-red-500' 
    : 'border-gray-300 focus:ring-blue-500 focus:border-blue-500';
  $: disabledClasses = disabled ? 'bg-gray-100 cursor-not-allowed' : 'bg-white';
  $: iconClasses = icon ? 'pl-10' : '';
  $: selectClasses = `${baseClasses} ${stateClasses} ${disabledClasses} ${iconClasses} pr-10`;

  // Get selected option for display
  $: selectedOption = options.find(opt => opt.value === value);
</script>

<div class="w-full">
  <!-- Label -->
  {#if label}
    <label for={selectId} class="block text-sm font-medium text-gray-700 mb-2">
      {label}
      {#if required}
        <span class="text-red-500 ml-1">*</span>
      {/if}
    </label>
  {/if}

  <!-- Select container -->
  <div class="relative">
    <!-- Icon -->
    {#if icon}
      <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
        <Icon icon={icon} class="w-4 h-4 text-gray-400" />
      </div>
    {/if}

    <!-- Select field -->
    <select
      id={selectId}
      bind:value
      {required}
      {disabled}
      class={selectClasses}
      on:change={handleChange}
      on:blur={handleBlur}
      on:focus={handleFocus}
    >
      {#if placeholder}
        <option value="" disabled selected={!value}>
          {placeholder}
        </option>
      {/if}
      
      {#each options as option (option.value)}
        <option 
          value={option.value} 
          disabled={option.disabled}
          selected={option.value === value}
        >
          {option.label}
        </option>
      {/each}
    </select>

    <!-- Dropdown arrow -->
    <div class="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
      <Icon icon="material-symbols:keyboard-arrow-down" class="w-5 h-5 text-gray-400" />
    </div>
  </div>

  <!-- Description for selected option -->
  {#if selectedOption?.description}
    <div class="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <p class="text-sm text-blue-800">
        <Icon icon="material-symbols:info" class="w-4 h-4 inline mr-1" />
        {selectedOption.description}
      </p>
    </div>
  {/if}

  <!-- Helper text and error -->
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
</div>