import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface ChatMessage {
	sender: 'user' | 'bot';
	text: string;
}

@Component({
	selector: 'app-gem',
	imports: [CommonModule, FormsModule],
	templateUrl: './gem.html',
	styleUrl: './gem.css',
})
export class Gem {
	private http = inject(HttpClient);
	private apiBaseUrl = 'http://localhost:8000/api';

	// State Management with Signals
	selectedFile = signal<File | null>(null);
	isUploading = signal<boolean>(false);
	isQuerying = signal<boolean>(false);
	statusMessage = signal<string>('');
	chatHistory = signal<ChatMessage[]>([]);
	userQuery = signal<string>('');

	onFileSelected(event: Event): void {
		const input = event.target as HTMLInputElement;
		if (input.files && input.files.length > 0) {
			this.selectedFile.set(input.files[0]);
			this.statusMessage.set(`Target file targeted: ${input.files[0].name}`);
		}
	}

	uploadDocument(): void {
		const fileToUpload = this.selectedFile();
		if (!fileToUpload) return;

		this.isUploading.set(true);
		this.statusMessage.set("Uploading... Extracting segments & calculating embeddings.");

		const formData = new FormData();
		formData.append('file', fileToUpload);

		this.http.post<{ message: string; chunks: number }>(`${this.apiBaseUrl}/upload`, formData)
			.subscribe({
				next: (res) => {
					this.statusMessage.set(`Success!\n${res.message}\nGenerated Vectors: ${res.chunks} units.`);
					this.isUploading.set(false);
				},
				error: (err) => {
					this.statusMessage.set(`Pipeline error: ${err.error?.detail || 'Vector setup failed.'}`);
					this.isUploading.set(false);
				}
			});
	}

	sendQuery(): void {
		const queryText = this.userQuery().trim();
		if (!queryText || this.isQuerying()) return;

		// Append user question to stream array context natively via update()
		this.chatHistory.update(history => [...history, { sender: 'user', text: queryText }]);
		this.userQuery.set('');
		this.isQuerying.set(true);

		this.http.post<{ answer: string }>(`${this.apiBaseUrl}/chat`, { question: queryText })
			.subscribe({
				next: (res) => {
					this.chatHistory.update(history => [...history, { sender: 'bot', text: res.answer }]);
					this.isQuerying.set(false);
				},
				error: (err) => {
					const errMsg = err.error?.detail || 'Fatal disconnect while asking local processing model.';
					this.chatHistory.update(history => [...history, { sender: 'bot', text: `Error: ${errMsg}` }]);
					this.isQuerying.set(false);
				}
			});
	}
}
