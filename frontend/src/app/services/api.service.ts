import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({
	providedIn: 'root'
})
export class ApiService {

	private http = inject(HttpClient);

	apiUrl = 'http://localhost:8000';

	uploadPdf(file: File) {

		const formData = new FormData();

		formData.append(
			'file',
			file
		);

		return this.http.post(
			`${this.apiUrl}/upload`,
			formData
		);
	}

	processPdf(fileName: string) {

		return this.http.post(
			`${this.apiUrl}/process-pdf?file_name=${fileName}`,
			{}
		);
	}

	embedPdf(fileName: string) {

		return this.http.post(
			`${this.apiUrl}/embed-pdf?file_name=${fileName}`,
			{}
		);
	}

	chat(question: string) {

		return this.http.post(
			`${this.apiUrl}/chat?question=${encodeURIComponent(question)}`,
			{}
		);
	}
}
