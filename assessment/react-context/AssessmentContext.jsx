import { createContext, useState } from 'react';

// 1. Create the context
//    Hint: createContext() can take a default value, but for this pattern
//    we typically pass undefined so we can detect misuse later.
const AssessmentContext = createContext(undefined);

// 2. Create the provider component
function AssessmentProvider({ children }) {

  const [responses, setResponses] = useState([]);
  const [currentStep, setCurrentSetp] = useState(0);

  const addResponse = (questionId, answer, score) => {
    setResponses(prev => [...prev, {questionId, answer, score}]);
  }

  const nextStep = () => {
    setCurrentSetp(prev => prev +1);
  }

  const resetAssessment= () => {
    setResponses([]);
    setCurrentSetp(0);
  }


  return (
    <AssessmentContext.Provider value={{ responses, currentStep, addResponse, nextStep, resetAssessment}}>
      {children}
    </AssessmentContext.Provider>
  );
}

const useAssesment = () => {
  
  if (useContext(AssessmentContext) === undefined){
    throw new Error("Error descriptive");
  }
  return useContext(AssessmentContext);

  }

export { AssessmentContext, AssessmentProvider, useAssesment };

