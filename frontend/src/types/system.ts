export interface SystemCapabilities {
  receipt_extraction_provider: 'mock' | 'local' | 'openai'
  receipt_extraction_mode: 'demo' | 'local' | 'ai'
  real_ai_enabled: boolean
  ollama_available: boolean | null
  tesseract_available: boolean | null
}
