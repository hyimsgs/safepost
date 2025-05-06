import React, { useState } from 'react';
import './index.css';

function App() {
  const [image, setImage] = useState(null);
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    const reader = new FileReader();
    reader.onloadend = () => {
      setImage(reader.result.split(',')[1]);
    };
    if (file) reader.readAsDataURL(file);
  };

  const handleAnalyze = async () => {
    if (!image) return alert('이미지를 업로드해주세요.');
    setLoading(true);
    try {
      const response = await fetch("https://safepost.onrender.com/analyze", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image, caption: '' })
      });
      const data = await response.json();
      setResult(data.result);
    } catch (err) {
      alert('분석 실패');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const extractAnalysis = (text) => {
    const scoreMatch = text.match(/싫어하지 않을 확률:\s*(\d+)/);
    const warningMatch = text.match(/경고:\s*(.*)/);
    const recommendationMatch = text.match(/추천:\s*(.*)/);

    const score = scoreMatch ? parseInt(scoreMatch[1], 10) : null;
    const warning = warningMatch ? warningMatch[1].trim() : null;
    const recommendation = recommendationMatch ? recommendationMatch[1].trim() : null;

    return { score, warning, recommendation };
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-200 via-purple-300 to-blue-300 flex items-center justify-center px-4 py-12 text-gray-800">
      <div className="bg-white rounded-3xl shadow-2xl p-10 max-w-md w-full">
        <h1 className="text-4xl font-extrabold text-center text-indigo-700 mb-2 tracking-tight">SafePost 🌟</h1>
        <p className="text-center text-sm text-gray-500 mb-8">업로드 전에, 당신의 게시물을 안전하게 점검하세요.</p>

        <label className="border-2 border-dashed border-gray-300 rounded-xl p-5 w-full text-center cursor-pointer hover:border-indigo-400 transition block">
          <input type="file" accept="image/*" onChange={handleImageChange} className="hidden" />
          {image ? '✅ 이미지 선택 완료' : '📷 여기에 이미지를 업로드해보세요'}
        </label>

        {image && (
          <div className="mt-6 rounded-xl overflow-hidden shadow-md animate-fade-in">
            <img
              src={`data:image/jpeg;base64,${image}`}
              alt="업로드된 이미지"
              className="w-full object-cover max-h-96"
            />
          </div>
        )}

        <button
          onClick={handleAnalyze}
          disabled={loading}
          className="mt-6 bg-indigo-600 hover:bg-indigo-700 text-white w-full py-3 rounded-xl text-lg font-semibold transition"
        >
          {loading ? '분석 중...' : '✨ 분석하기'}
        </button>

        {result && (
          <div className="mt-8 bg-gray-100 p-5 rounded-xl">
            <h3 className="text-xl font-semibold mb-3">📊 분석 결과</h3>

            {(() => {
              const { score, warning, recommendation } = extractAnalysis(result);
              if (score !== null && warning && recommendation) {
                return (
                  <pre className="whitespace-pre-wrap text-sm font-medium text-gray-700">
📊 이 게시물은 {score}% 확률로 안전합니다.
🛑 경고: {warning}
✨ 추천: {recommendation}
                  </pre>
                );
              } else {
                return <pre className="text-sm text-red-500">결과를 불러올 수 없습니다.</pre>;
              }
            })()}

          </div>
        )}
      </div>
    </div>
  );
}

export default App;
