import { useAssesment } from './AssessmentContext';

const ProgressBar = () => {
  const context = useAssesment();

  const nresponses = context.responses.length;
  return (
    <div>
      Step: {context.currentStep} | responses: {nresponses}
    </div>
  );
};

export default ProgressBar;
