from typing import Dict, List, Any

class XAIExplainer:
    def explain_recommendation(self,topic_id,topic_name,student_profile,q_value,current_mastery):
        reasons=[]; factors={}
        if current_mastery<0.3: reasons.append(f"You have not started {topic_name} yet"); factors["mastery_gap"]=1.0-current_mastery
        elif current_mastery<0.6: reasons.append(f"Mastery at {current_mastery:.0%} â€” room to improve"); factors["mastery_gap"]=1.0-current_mastery
        if student_profile.get("irt_ability",0)>0.5: reasons.append("Your ability score shows readiness"); factors["ability_readiness"]=0.8
        if student_profile.get("engagement_score",0.5)>0.7: reasons.append("High engagement â€” good time for new material"); factors["engagement"]=student_profile["engagement_score"]
        if topic_id in student_profile.get("knowledge_gaps",[]): reasons.append("Identified as a knowledge gap"); factors["knowledge_gap"]=1.0
        reasons.append("All prerequisites meet mastery threshold"); factors["prereq_readiness"]=0.9
        total=sum(factors.values()) or 1
        return {"topic_id":topic_id,"topic_name":topic_name,"confidence":round(min(abs(q_value)/3+0.5,1),2),"primary_reason":reasons[0] if reasons else "Based on your profile","all_reasons":reasons,"contributing_factors":factors,"feature_attributions":[{"feature":k.replace("_"," ").title(),"value":round(v,3),"percentage":round(v/total*100,1)} for k,v in sorted(factors.items(),key=lambda x:-x[1])]}

xai_explainer = XAIExplainer()
