/**
 * Classification store for managing categories and classification results
 */

import { writable, derived } from 'svelte/store';
import type {
  CategoryResponse,
  ClassificationResponse,
  ClassificationModelInfo,
  CategoryCreate,
  CategoryUpdate
} from '../services/api';
import { api } from '../services/api';
import { notifications } from './notifications';

// Store for categories
export const categories = writable<CategoryResponse[]>([]);

// Store for classification results
export const classificationResults = writable<ClassificationResponse | null>(null);

// Store for available models
export const classificationModels = writable<ClassificationModelInfo[]>([]);

// Store for selected model
export const selectedModel = writable<string>('embeddinggemma:latest');

// Store for loading states
export const isLoadingCategories = writable<boolean>(false);
export const isLoadingClassification = writable<boolean>(false);
export const isLoadingModels = writable<boolean>(false);

// Store for form states
export const isCreatingCategory = writable<boolean>(false);
export const isUpdatingCategory = writable<boolean>(false);

// Derived store for categories count
export const categoriesCount = derived(categories, ($categories) => $categories.length);

// Derived store for checking if categories exist
export const hasCategories = derived(categories, ($categories) => $categories.length > 0);

// Actions
export const classificationStore = {
  // Load all categories
  async loadCategories() {
    isLoadingCategories.set(true);
    try {
      const data = await api.getCategories();
      categories.set(data);
    } catch (error) {
      console.error('Failed to load categories:', error);
      notifications.addError('Failed to load categories');
    } finally {
      isLoadingCategories.set(false);
    }
  },

  // Create a new category
  async createCategory(categoryData: CategoryCreate): Promise<boolean> {
    isCreatingCategory.set(true);
    try {
      const newCategory = await api.createCategory(categoryData);
      categories.update(cats => [...cats, newCategory]);
      notifications.addSuccess(`Category "${newCategory.name}" created successfully`);
      return true;
    } catch (error) {
      console.error('Failed to create category:', error);
      notifications.addError('Failed to create category');
      return false;
    } finally {
      isCreatingCategory.set(false);
    }
  },

  // Update an existing category
  async updateCategory(categoryId: number, categoryData: CategoryUpdate): Promise<boolean> {
    isUpdatingCategory.set(true);
    try {
      const updatedCategory = await api.updateCategory(categoryId, categoryData);
      categories.update(cats =>
        cats.map(cat => cat.id === categoryId ? updatedCategory : cat)
      );
      notifications.addSuccess(`Category "${updatedCategory.name}" updated successfully`);
      return true;
    } catch (error) {
      console.error('Failed to update category:', error);
      notifications.addError('Failed to update category');
      return false;
    } finally {
      isUpdatingCategory.set(false);
    }
  },

  // Delete a category
  async deleteCategory(categoryId: number): Promise<boolean> {
    try {
      await api.deleteCategory(categoryId);
      categories.update(cats => cats.filter(cat => cat.id !== categoryId));
      notifications.addSuccess('Category deleted successfully');
      return true;
    } catch (error) {
      console.error('Failed to delete category:', error);
      notifications.addError('Failed to delete category');
      return false;
    }
  },

  // Classify text
  async classifyText(text: string, model?: string, topK?: number): Promise<boolean> {
    if (!text.trim()) {
      notifications.addWarning('Please enter text to classify');
      return false;
    }

    isLoadingClassification.set(true);
    try {
      const response = await api.classifyText({
        text: text.trim(),
        model: model,
        top_k: topK || 5
      });
      classificationResults.set(response);
      return true;
    } catch (error) {
      console.error('Failed to classify text:', error);
      notifications.addError('Failed to classify text');
      classificationResults.set(null);
      return false;
    } finally {
      isLoadingClassification.set(false);
    }
  },

  // Load available models
  async loadModels() {
    isLoadingModels.set(true);
    try {
      const models = await api.getClassificationModels();
      classificationModels.set(models);

      // Set default model if not already selected
      if (models.length > 0) {
        selectedModel.update(current => {
          if (!current || !models.find(m => m.name === current)) {
            return models[0].name;
          }
          return current;
        });
      }
    } catch (error) {
      console.error('Failed to load models:', error);
      notifications.addError('Failed to load available models');
    } finally {
      isLoadingModels.set(false);
    }
  },

  // Clear classification results
  clearResults() {
    classificationResults.set(null);
  },

  // Reset all stores
  reset() {
    categories.set([]);
    classificationResults.set(null);
    classificationModels.set([]);
    selectedModel.set('embeddinggemma:latest');
    isLoadingCategories.set(false);
    isLoadingClassification.set(false);
    isLoadingModels.set(false);
    isCreatingCategory.set(false);
    isUpdatingCategory.set(false);
  }
};