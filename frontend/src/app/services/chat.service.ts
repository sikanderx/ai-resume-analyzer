import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })

export class ChatService {

	async streamMessage(message: string, onChunk: (text: string) => void) {
		try {
			const response = await fetch('http://localhost:3000/chat', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ message })
			});

			if (!response.ok) {
				console.error('Server returned an error:', response.statusText);
				return;
			}

			const reader = response.body?.getReader();
			const decoder = new TextDecoder('utf-8');

			if (!reader) {
				console.error('Streams are not supported or response body is empty.');
				return;
			}

			while (true) {
				const { value, done } = await reader.read();
				if (done) break;

				const chunk = decoder.decode(value, { stream: true });

				if (chunk) {
					onChunk(chunk);
				}
			}

			const finalChunk = decoder.decode();
			if (finalChunk) {
				onChunk(finalChunk);
			}

		} catch (error) {
			console.error('Streaming failed on frontend:', error);
		}
	}
}
