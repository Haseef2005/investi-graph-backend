import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, Trash2, MessageSquare, LogOut, Globe, Download } from 'lucide-react';
import api from '../services/api';

export default function Dashboard() {
    const [documents, setDocuments] = useState([]);
    const [uploading, setUploading] = useState(false);
    const [showSecModal, setShowSecModal] = useState(false);
    const [secLoading, setSecLoading] = useState(false);
    const [ticker, setTicker] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        fetchDocuments();
        // Poll for updates every 5 seconds to check for new SEC imports or processed files
        const interval = setInterval(fetchDocuments, 5000);
        return () => clearInterval(interval);
    }, []);

    const fetchDocuments = async () => {
        try {
            const response = await api.get('/documents/');
            setDocuments(response.data);
        } catch (error) {
            console.error('Failed to fetch documents', error);
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            // Add a minimum delay to ensure the loading state is visible
            await Promise.all([
                api.post('/documents/', formData),
                new Promise(resolve => setTimeout(resolve, 1000))
            ]);
            await fetchDocuments();
        } catch (error) {
            console.error('Upload failed', error);
        } finally {
            setUploading(false);
        }
    };

    const handleSecImport = async (e) => {
        e.preventDefault();
        if (!ticker) return;

        setSecLoading(true);
        const initialCount = documents.length;

        try {
            await api.post('/documents/fetch-sec', { ticker });

            // Poll until a new document appears (max 60 seconds)
            let attempts = 0;
            const maxAttempts = 30; // 30 * 2s = 60s

            const pollForNewDoc = async () => {
                if (attempts >= maxAttempts) {
                    throw new Error('Timeout waiting for document');
                }

                const response = await api.get('/documents/');
                const newDocs = response.data;

                if (newDocs.length > initialCount) {
                    setDocuments(newDocs);
                    return;
                }

                attempts++;
                await new Promise(resolve => setTimeout(resolve, 2000));
                await pollForNewDoc();
            };

            await pollForNewDoc();

            setShowSecModal(false);
            setTicker('');
        } catch (error) {
            console.error('SEC fetch failed', error);
            alert('Failed to fetch SEC document or timed out');
        } finally {
            setSecLoading(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Are you sure?')) return;
        try {
            await api.delete(`/documents/${id}`);
            fetchDocuments();
        } catch (error) {
            console.error('Delete failed', error);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('token');
        navigate('/login');
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <nav className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                    <h1 className="text-2xl font-bold text-gray-900">InvestiGraph</h1>
                    <div className="flex items-center space-x-4">
                        <button
                            onClick={() => navigate('/chat/global')}
                            className="flex items-center bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition-colors shadow-sm"
                        >
                            <Globe className="w-5 h-5 mr-2" />
                            Global Chat
                        </button>
                        <button
                            onClick={handleLogout}
                            className="flex items-center text-gray-600 hover:text-red-600 transition-colors"
                        >
                            <LogOut className="w-5 h-5 mr-2" />
                            Logout
                        </button>
                    </div>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="flex justify-between items-center mb-8">
                    <h2 className="text-xl font-semibold text-gray-800">Your Documents</h2>
                    <div className="flex space-x-3">
                        <button
                            onClick={() => setShowSecModal(true)}
                            className="bg-gray-800 hover:bg-gray-900 text-white px-6 py-2 rounded-lg flex items-center transition-all shadow-md"
                        >
                            <Download className="w-5 h-5 mr-2" />
                            Import SEC 10-K
                        </button>
                        <label className={`cursor-pointer bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg flex items-center transition-all shadow-md ${uploading ? 'opacity-75 cursor-not-allowed' : ''}`}>
                            {uploading ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                                    Uploading...
                                </>
                            ) : (
                                <>
                                    <Upload className="w-5 h-5 mr-2" />
                                    Upload PDF
                                </>
                            )}
                            <input type="file" className="hidden" accept=".pdf" onChange={handleUpload} disabled={uploading} />
                        </label>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {documents.map((doc) => (
                        <div key={doc.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                            <div className="flex items-start justify-between mb-4">
                                <div className="p-3 bg-blue-50 rounded-lg">
                                    <FileText className="w-6 h-6 text-blue-600" />
                                </div>
                                <button
                                    onClick={() => handleDelete(doc.id)}
                                    className="text-gray-400 hover:text-red-500 transition-colors"
                                >
                                    <Trash2 className="w-5 h-5" />
                                </button>
                            </div>
                            <h3 className="font-medium text-gray-900 truncate mb-2" title={doc.filename}>
                                {doc.filename}
                            </h3>
                            <p className="text-sm text-gray-500 mb-4">
                                Uploaded {new Date(doc.created_at).toLocaleDateString()}
                            </p>
                            <button
                                onClick={() => navigate(`/chat/${doc.id}`)}
                                className="w-full flex items-center justify-center bg-gray-50 hover:bg-gray-100 text-gray-700 py-2 rounded-lg transition-colors border border-gray-200"
                            >
                                <MessageSquare className="w-4 h-4 mr-2" />
                                Chat with Doc
                            </button>
                        </div>
                    ))}
                </div>
            </main>

            {/* SEC Import Modal */}
            {showSecModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-2xl p-8 w-full max-w-md shadow-2xl">
                        <h3 className="text-2xl font-bold text-gray-900 mb-4">Import SEC 10-K</h3>
                        <p className="text-gray-600 mb-6">Enter the stock ticker symbol (e.g., AAPL, MSFT) to fetch the latest 10-K report.</p>
                        <form onSubmit={handleSecImport}>
                            <input
                                type="text"
                                placeholder="Ticker Symbol (e.g. AAPL)"
                                value={ticker}
                                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                                className="w-full bg-gray-50 border border-gray-300 text-gray-900 rounded-lg py-3 px-4 mb-6 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                autoFocus
                                disabled={secLoading}
                            />
                            <div className="flex justify-end space-x-3">
                                <button
                                    type="button"
                                    onClick={() => setShowSecModal(false)}
                                    className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                                    disabled={secLoading}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center"
                                    disabled={secLoading}
                                >
                                    {secLoading ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                                            Importing...
                                        </>
                                    ) : (
                                        'Import'
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
