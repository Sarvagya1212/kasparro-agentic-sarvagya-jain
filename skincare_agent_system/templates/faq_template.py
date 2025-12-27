"""
FAQ Template - Structures FAQ content into JSON format.
"""
from typing import Dict, Any, List
from .base_template import ContentTemplate


class FAQTemplate(ContentTemplate):
    """Template for FAQ page generation."""
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render FAQ data into structured JSON format.
        
        Expected data format:
        {
            "product_name": str,
            "qa_pairs": List[tuple[str, str]],  # [(question, answer), ...]
            "categories": Optional[Dict[str, List[int]]]  # category -> question indices
        }
        
        Returns:
            JSON-serializable FAQ structure
        """
        self.validate_required_fields(data, ["product_name", "qa_pairs"])
        
        # Build FAQ list
        faqs = []
        for i, (question, answer) in enumerate(data["qa_pairs"]):
            faq_item = {
                "id": i + 1,
                "question": question,
                "answer": answer
            }
            
            # Add category if available
            if "categories" in data:
                for category, indices in data["categories"].items():
                    if i in indices:
                        faq_item["category"] = category
                        break
            
            faqs.append(faq_item)
        
        return {
            "product": data["product_name"],
            "total_questions": len(faqs),
            "faqs": faqs,
            "generated_at": data.get("timestamp", "")
        }
